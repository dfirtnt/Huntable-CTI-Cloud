"""Hunt Scoring System - Exact replication from existing CTIScraper implementation

This is based on the ThreatHuntingScorer class from:
D:/Users/andrew.skatoff/CTISCraper/CTIScraper/src/utils/content.py (lines 575-941)
"""
import logging
import re
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


# Windows Malware Keywords for Threat Hunting Scoring
# Replicated exactly from existing implementation
WINDOWS_MALWARE_KEYWORDS = {
    'perfect_discriminators': [
        'rundll32.exe', 'comspec', 'msiexec.exe', 'wmic.exe', 'iex', 'findstr.exe',
        'hklm', 'appdata', 'programdata', 'powershell.exe', 'wbem',
        '.lnk', 'D:\\', 'C:\\', '.iso', '<Command>', 'MZ',
        'svchost.exe', '-accepteula', 'lsass.exe', 'WINDIR', 'wintmp',
        '\\temp\\', '\\pipe\\', '%WINDIR%', '%wintmp%', 'FromBase64String',
        'MemoryStream', 'New-Object', 'DownloadString', 'Defender query',
        'sptth',
        # Promoted from LOLBAS (100% avg scores in high-scoring articles)
        'reg.exe', 'winlogon.exe', 'conhost.exe', 'msiexec.exe', 'wscript.exe', 'services.exe', 'fodhelper',
        # Promoted from Good discriminators (100% avg scores)
        'EventCode', 'parent-child', 'KQL', '2>&1',
        # PowerShell attack techniques (100% chosen rate)
        'invoke-mimikatz', 'hashdump', 'invoke-shellcode', 'invoke-eternalblue',
        # Cmd.exe obfuscation regex patterns (basic threat techniques)
        r'%[A-Za-z0-9_]+:~[0-9]+(,[0-9]+)?%',  # env-var substring access
        r'%[A-Za-z0-9_]+:[^=%%]+=[^%]*%',  # env-var string substitution
        r'![A-Za-z0-9_]+!',  # delayed expansion markers
        r'\bcmd(\.exe)?\s*/V(?::[^ \t/]+)?',  # /V:ON obfuscated variants
        r'\bset\s+[A-Za-z0-9_]+\s*=',  # multiple SET stages
        r'\bcall\s+(set|%[A-Za-z0-9_]+%|![A-Za-z0-9_]+!)',  # CALL invocation
        r'(%[^%]+%){4,}',  # adjacent env-var concatenation
        r'\bfor\s+/?[A-Za-z]*\s+%[A-Za-z]\s+in\s*\(',  # FOR loops
        r'![A-Za-z0-9_]+:~%[A-Za-z],1!',  # FOR-indexed substring extraction
        r'\bfor\s+/L\s+%[A-Za-z]\s+in\s*\([^)]+\)',  # reversal via /L
        r'%[A-Za-z0-9_]+:~-[0-9]+%|%[A-Za-z0-9_]+:~[0-9]+%',  # tail trimming
        r'%[A-Za-z0-9_]+:\*[^!%]+=!%',  # asterisk-based substitution
        r'[^\w](s\^+e\^*t|s\^*e\^+t)[^\w]',  # caret-obfuscated set
        r'[^\w](c\^+a\^*l\^*l|c\^*a\^+l\^*l|c\^*a\^*l\^+l)[^\w]',  # caret-obfuscated call
        r'\^|"',  # caret or quote splitting
        r'%[^%]+%<[^>]*|set\s+[A-Za-z0-9_]+\s*=\s*[^&|>]*\|',  # stdin piping patterns
        # macOS-specific perfect discriminators (100% chosen rate)
        'homebrew', '/users/shared/', 'chmod 777',
        # macOS telemetry and security controls (100% chosen rate)
        'tccd', 'spctl', 'csrutil',
        # Added from non-English word analysis
        'xor',
        # High-performing keywords from analysis (80%+ chosen rate)
        'tcp://', 'CN=', '-ComObject', 'Chcp', 'tostring', 'HKCU', 'System32',
        'Hxxp', 'Cmd', '8080', 'XOR', 'User-Agent', 'sshd', 'Base64',
        # Perfect threat hunting discriminators (>75% in 90+ hunt score range)
        'icacls', 'InteropServices.Marshal', 'selection1:', 'dclist', 'invoke-',
        'tasklist', 'adfind', '-EncodedCommand', 'selection_1:', 'attrib',
        'ParentImage', 'CommandLine',
        # Low-rejection keywords from analysis (0-2 rejected)
        'System.IO', 'New-Object', 'StreamReader', 'ByteArray', '127.0.0.1', '>1', 'admin$',
        'MpPreference', 'Whoami', 'C$', 'MSBuild', '7z',
        # High-performing non-Windows keywords (>90% chosen rate)
        'auditd', 'systemd', 'xattr', 'EndpointSecurity', 'osquery',
        'zeek', 'dns_query', 'ja3',
        # WMI reconnaissance patterns (high threat hunting value)
        'SELECT * FROM'
    ],
    'good_discriminators': [
        'temp', '==', 'c:\\windows\\', 'Event ID', '.bat', '.ps1',
        'pipe', '::', '[.]', '-->', 'currentversion',
        'Monitor', 'Executable', 'Detection', 'Alert on', 'Hunt for',
        'Hunting', 'Create Detections', 'Search Query', '//',
        'http:', 'hxxp', '->', '.exe', '--',
        '\\\\', 'spawn', '|',
        # PowerShell attack techniques (high chosen rate)
        'mimikatz', 'kerberoast', 'psexec',
        # macOS-specific good discriminators (high chosen rate)
        'mach-o', 'plist',
        # macOS attack vectors and telemetry (60%+ chosen rate)
        'osascript', 'TCC.db',
        # Added from non-English word analysis
        'payload', 'sftp', 'downloader', 'jss',
        # Character pattern discriminators (high correlation analysis)
        '{}', '<>', '[]',
        # Medium-performing keywords from analysis (50%+ chosen rate)
        'win32_', 'Httpd', 'Int64', '/usr/', 'echo', '/tmp/', '/etc/',
        # Additional non-Windows keywords for comprehensive coverage
        'syslog', 'sudo', 'cron', 'LD_PRELOAD', 'launchd',
        'auditlog', 'iam', 'snort', 'proxy', 'http_request', 'anomaly',
        'linux', 'macos', 'cloud', 'aws', 'azure', 'network', 'ssl',
        # Moved from Perfect (didn't meet 90% threshold)
        'codesign', 'cloudtrail', 'guardduty', 's3', 'ec2', 'gcp',
        'suricata', 'netflow', 'beaconing', 'user-agent',
        # Good threat hunting discriminators (≤75% in 90+ hunt score range)
        'process_creation', 'reg add', 'logsource:', 'get-', 'selection:',
        'DeviceProcessEvents', 'hxxps', 'taskkill.exe', 'detection:', 'DeviceFileEvents',
        'child'
    ],
    'intelligence_indicators': [
        # Real threat activity - specific indicators
        'APT', 'threat actor', 'attribution', 'campaign', 'incident',
        'breach', 'compromise', 'malware family', 'IOC', 'indicator',
        'TTP', 'technique', 'observed', 'discovered', 'detected in wild',
        'real-world', 'in the wild', 'in-the-wild', 'active campaign', 'ongoing threat',
        'victim', 'targeted', 'exploited', 'compromised', 'infiltrated',

        # Attack lifecycle phases (high-priority additions)
        'intrusion', 'beacon', 'lateral movement', 'persistence', 'reconnaissance',
        'exfiltration', 'command and control', 'c2', 'initial access', 'privilege escalation',

        # Specific threat groups
        'FIN', 'TA', 'UNC', 'APT1', 'APT28', 'APT29', 'Lazarus', 'Carbanak',
        'Cozy Bear', 'Fancy Bear', 'Wizard Spider', 'Ryuk', 'Maze',

        # Real incidents and attacks
        'ransomware', 'data breach', 'cyber attack', 'espionage',
        'sophisticated attack', 'advanced persistent threat',

        # Rare Kerberos attack techniques (future content detection)
        'golden-ticket', 'silver-ticket'
    ],
    'negative_indicators': [
        # Educational/marketing content that should be penalized
        'what is', 'how to', 'guide to', 'tutorial', 'best practices',
        'statistics', 'survey', 'report shows', 'study reveals',
        'learn more', 'read more', 'click here', 'download now',
        'free trial', 'contact us', 'get started', 'sign up',
        'blog post', 'newsletter', 'webinar', 'training',
        'overview', 'introduction', 'basics', 'fundamentals'
    ],
    'lolbas_executables': [
        'certutil.exe', 'cmd.exe', 'schtasks.exe', 'wmic.exe', 'bitsadmin.exe', 'ftp.exe', 'netsh.exe', 'cscript.exe', 'mshta.exe',
        'regsvr32.exe', 'rundll32.exe', 'forfiles.exe', 'explorer.exe', 'ieexec.exe', 'powershell.exe', 'conhost.exe', 'svchost.exe', 'lsass.exe',
        'csrss.exe', 'smss.exe', 'wininit.exe', 'nltest.exe', 'odbcconf.exe', 'scrobj.dll', 'addinutil.exe', 'appinstaller.exe', 'aspnet_compiler.exe',
        'atbroker.exe', 'bash.exe', 'certoc.exe', 'certreq.exe', 'cipher.exe', 'cmdkey.exe', 'cmdl32.exe', 'cmstp.exe', 'colorcpl.exe',
        'computerdefaults.exe', 'configsecuritypolicy.exe', 'control.exe', 'csc.exe', 'customshellhost.exe', 'datasvcutil.exe',
        'desktopimgdownldr.exe', 'devicecredentialdeployment.exe', 'dfsvc.exe', 'diantz.exe', 'diskshadow.exe', 'dnscmd.exe', 'esentutl.exe',
        'eventvwr.exe', 'expand.exe', 'extexport.exe', 'extrac32.exe', 'findstr.exe', 'finger.exe', 'fltmc.exe', 'gpscript.exe',
        'replace.exe', 'sc.exe', 'print.exe', 'ssh.exe', 'teams.exe', 'rdrleakdiag.exe', 'ipconfig.exe', 'systeminfo.exe',
        'aspnet_com.exe', 'acroreer.exe', 'change.exe', 'configse.exe', 'customshell.exe', 'datasecutil.exe', 'desktopimg.exe',
        'devicescred.exe', 'dism.exe', 'eudcedit.exe', 'export.exe', 'finger.exe', 'flmc.exe', 'fsutil.exe', 'gscript.exe', 'hh.exe', 'imewdbld.exe',
        'ie4uinit.exe', 'inetcpl.exe', 'installutil.exe', 'iscsicpl.exe', 'isc.exe', 'ldifde.exe', 'makecab.exe', 'mavinject.exe',
        'microsoft.workflow.exe', 'mmc.exe', 'mpcmdrun.exe', 'msbuild.exe', 'msconfig.exe', 'msdt.exe', 'msedge.exe', 'ngen.exe',
        'offlinescanner.exe', 'onedrivesta.exe', 'pcalua.exe', 'pcwrun.exe', 'platman.exe', 'pnputil.exe', 'presentationsettings.exe',
        'print.exe', 'printbrm.exe', 'prowlaunch.exe', 'psr.exe', 'query.exe', 'rasautou.exe', 'rdrleakdiag.exe', 'reg.exe', 'regasm.exe', 'regedit.exe',
        'regini.exe', 'register-cim.exe', 'replace.exe', 'reset.exe', 'rpcping.exe', 'runschlp.exe', 'runonce.exe', 'runscripthelper.exe',
        'scriptrunner.exe', 'setres.exe', 'settingsynchost.exe', 'sftp.exe', 'syncappvpublishingserver.exe', 'tar.exe', 'tldinject.exe',
        'tracerpt.exe', 'unregmp2.exe', 'wbc.exe', 'vssadmin.exe', 'wab.exe', 'wbadmin.exe', 'wbemtest.exe', 'wfgen.exe', 'wfp.exe', 'winword.exe',
        'wsreset.exe', 'wuzucht.exe', 'xwizard.exe', 'msedge_proxy.exe', 'msedgewebview2.exe', 'wsl.exe', 'adxpack.dll', 'desk.cpl', 'ieframe.dll',
        'mshtml.dll', 'pcwutil.dll', 'photoviewer.dll', 'setupapi.dll', 'shdocvw.dll', 'shell32.dll', 'shimgvw.dll', 'syssetup.dll', 'url.dll',
        'zipfldr.dll', 'comsvcs.dll', 'acccheckco.dll', 'adplus.exe', 'agentexecu.exe', 'applauncher.exe', 'appcert.exe', 'appvlp.exe', 'bginfo.exe',
        'cdb.exe', 'coregen.exe', 'createdump.exe', 'csi.exe', 'defaultpack.exe', 'devinit.exe', 'devtroubleshoot.exe', 'dnx.exe', 'dotnet.exe',
        'dpubuild.exe', 'dputil.exe', 'dump64.exe', 'dumpmini.exe', 'dxcap.exe', 'ecmangen.exe', 'excel.exe', 'foj.exe', 'fsrmgpu.exe', 'hltrace.exe',
        'microsoft.notes.exe', 'mpiexec.exe', 'msaccess.exe', 'msdeploy.exe', 'msohtmed.exe', 'mspub.exe', 'mses.exe', 'ndsutil.exe', 'ntds.exe',
        'openconsole.exe', 'pstools.exe', 'powerpnt.exe', 'procdump.exe', 'protocolhandler.exe', 'rcsi.exe', 'remote.exe', 'sqldumper.exe',
        'sqlps.exe', 'sqltoolsps.exe', 'squirrel.exe', 'ta.exe', 'teams.exe', 'testwindow.exe', 'tracker.exe', 'update.exe', 'vsdiagnostic.exe',
        'vsixinstaller.exe', 'visio.exe', 'visualuiaver.exe', 'vsixlaunch.exe', 'vsshadow.exe', 'wsgldebugger.exe', 'wfhformat.exe', 'wic.exe',
        'windbg.exe', 'winproj.exe', 'xbootmgr.exe', 'xtoolmgr.exe', 'rdptunnel.exe', 'wslg-agent.exe', 'wstest_console.exe', 'winfile.exe',
        'xsd.exe', 'cl_loadas.exe', 'cl_mute.exe', 'cl_invoca.exe', 'launch-vsd.exe', 'manage-bde.exe', 'pubprn.vbs', 'syncappvpu.exe',
        'utilityfunc.exe', 'winrm.vbs', 'poster.bat'
    ],
}


class HuntScorer:
    """Enhanced scoring for threat hunting and malware analysis content.

    This is an exact replication of the ThreatHuntingScorer class from the existing
    CTIScraper implementation, adapted to the new codebase structure.
    """

    @staticmethod
    def score_article(title: str, summary: str, content: str = None) -> Dict[str, Any]:
        """
        Score content for threat hunting quality using Windows malware keywords.

        Args:
            title: Article title
            summary: Article summary/excerpt
            content: Full article content (optional)

        Returns:
            Dict containing:
            - threat_hunting_score: float (0-100)
            - perfect_keyword_matches: List[str]
            - good_keyword_matches: List[str]
            - lolbas_matches: List[str]
            - intelligence_matches: List[str]
            - negative_matches: List[str]
        """
        if not content and not summary:
            return {
                'threat_hunting_score': 0.0,
                'perfect_keyword_matches': [],
                'good_keyword_matches': [],
                'lolbas_matches': [],
                'intelligence_matches': [],
                'negative_matches': []
            }

        # Combine title and content for analysis (lowercase for matching)
        title_lower = title.lower() if title else ""
        summary_lower = summary.lower() if summary else ""
        content_lower = content.lower() if content else ""

        # Combine all text
        full_text = f"{title_lower} {summary_lower} {content_lower}"

        # Find keyword matches
        perfect_matches = []
        good_matches = []
        lolbas_matches = []
        intelligence_matches = []

        # Check perfect discriminators
        for keyword in WINDOWS_MALWARE_KEYWORDS['perfect_discriminators']:
            if HuntScorer._keyword_matches(keyword, full_text):
                perfect_matches.append(keyword)

        # Check good discriminators
        for keyword in WINDOWS_MALWARE_KEYWORDS['good_discriminators']:
            if HuntScorer._keyword_matches(keyword, full_text):
                good_matches.append(keyword)

        # Check LOLBAS executables
        for executable in WINDOWS_MALWARE_KEYWORDS['lolbas_executables']:
            if HuntScorer._keyword_matches(executable, full_text):
                lolbas_matches.append(executable)

        # Check intelligence indicators
        for indicator in WINDOWS_MALWARE_KEYWORDS['intelligence_indicators']:
            if HuntScorer._keyword_matches(indicator, full_text):
                intelligence_matches.append(indicator)

        # Check negative indicators (penalize educational/marketing content)
        negative_matches = []
        for negative in WINDOWS_MALWARE_KEYWORDS['negative_indicators']:
            if HuntScorer._keyword_matches(negative, full_text):
                negative_matches.append(negative)

        # Calculate scores using geometric series with 50% diminishing returns
        # Each successive match adds 50% of the previous increment
        # Formula: score = max_points * (1 - 0.5^n) where n = number of matches
        # This ensures scores approach but never reach the category maximum

        def geometric_score(matches: int, max_points: float) -> float:
            """Calculate score using geometric series that never reaches max."""
            if matches == 0:
                return 0.0
            # Score = max_points * (1 - 0.5^n)
            # As n increases, 0.5^n approaches 0, so score approaches max_points but never reaches it
            return max_points * (1.0 - (0.5 ** matches))

        # Perfect Discriminators: 75 points max (dominant weight for technical depth)
        perfect_score = geometric_score(len(perfect_matches), 75.0)

        # LOLBAS Executables: 10 points max (practical attack techniques)
        lolbas_score = geometric_score(len(lolbas_matches), 10.0)

        # Intelligence Indicators: 10 points max (core threat intelligence value)
        intelligence_score = geometric_score(len(intelligence_matches), 10.0)

        # Good Discriminators: 5 points max (supporting technical content)
        good_score = geometric_score(len(good_matches), 5.0)

        # Negative Penalties: -10 points max (educational/marketing content penalty)
        negative_penalty = geometric_score(len(negative_matches), 10.0)

        # Calculate final threat hunting score (0-100 range, but will never reach 100)
        # Theoretical max: 75 + 5 + 10 + 10 = 100, but geometric series ensures it never reaches 100
        # Cap at 99.9 to prevent rounding to 100.0
        threat_hunting_score = max(0.0, min(99.9, perfect_score + good_score + lolbas_score + intelligence_score - negative_penalty))

        return {
            'threat_hunting_score': round(threat_hunting_score, 1),
            'perfect_keyword_matches': perfect_matches,
            'good_keyword_matches': good_matches,
            'lolbas_matches': lolbas_matches,
            'intelligence_matches': intelligence_matches,
            'negative_matches': negative_matches
        }

    @staticmethod
    def _keyword_matches(keyword: str, text: str) -> bool:
        """
        Check if keyword matches in text using word boundaries or regex patterns.

        Args:
            keyword: Keyword to search for (can be regex pattern)
            text: Text to search in

        Returns:
            True if keyword is found with proper word boundaries or regex match
        """
        # Regex patterns for cmd.exe obfuscation techniques
        regex_patterns = [
            r'%[A-Za-z0-9_]+:~[0-9]+(,[0-9]+)?%',  # env-var substring access
            r'%[A-Za-z0-9_]+:[^=%%]+=[^%]*%',  # env-var string substitution
            r'![A-Za-z0-9_]+!',  # delayed expansion markers
            r'\bcmd(\.exe)?\s*/V(?::[^ \t/]+)?',  # /V:ON obfuscated variants
            r'\bset\s+[A-Za-z0-9_]+\s*=',  # multiple SET stages
            r'\bcall\s+(set|%[A-Za-z0-9_]+%|![A-Za-z0-9_]+!)',  # CALL invocation
            r'(%[^%]+%){4,}',  # adjacent env-var concatenation
            r'\bfor\s+/?[A-Za-z]*\s+%[A-Za-z]\s+in\s*\(',  # FOR loops
            r'![A-Za-z0-9_]+:~%[A-Za-z],1!',  # FOR-indexed substring extraction
            r'\bfor\s+/L\s+%[A-Za-z]\s+in\s*\([^)]+\)',  # reversal via /L
            r'%[A-Za-z0-9_]+:~-[0-9]+%|%[A-Za-z0-9_]+:~[0-9]+%',  # tail trimming
            r'%[A-Za-z0-9_]+:\*[^!%]+=!%',  # asterisk-based substitution
            r'[^\w](s\^+e\^*t|s\^*e\^+t)[^\w]',  # caret-obfuscated set
            r'[^\w](c\^+a\^*l\^*l|c\^*a\^+l\^*l|c\^*a\^*l\^+l)[^\w]',  # caret-obfuscated call
            r'[^\w]([a-z]\^+[a-z](\^+[a-z])*)[^\w]',  # caret-obfuscated commands (any length)
            r'%[^%]+%<[^>]*|set\s+[A-Za-z0-9_]+\s*=\s*[^&|>]*\|'  # stdin piping patterns
        ]

        # Check if keyword is a regex pattern
        if keyword in regex_patterns:
            return bool(re.search(keyword, text, re.IGNORECASE))

        # Get regex pattern for matching
        pattern = HuntScorer._build_keyword_pattern(keyword)

        return bool(re.search(pattern, text, re.IGNORECASE))

    @staticmethod
    def _build_keyword_pattern(keyword: str) -> str:
        """
        Build regex pattern for keyword matching.
        Shared logic used by both scoring and highlighting.

        Args:
            keyword: Keyword to build pattern for

        Returns:
            Regex pattern string
        """
        # Escape special regex characters for literal matching
        escaped_keyword = re.escape(keyword)

        # For certain keywords, allow partial matches (like "hunting" in "threat hunting")
        partial_match_keywords = ['hunting', 'detection', 'monitor', 'alert', 'executable', 'parent-child', 'defender query']

        # For wildcard keywords, use prefix matching
        wildcard_keywords = ['spawn']

        # For symbol keywords and path prefixes, don't use word boundaries
        symbol_keywords = ['==', '!=', '<=', '>=', '::', '-->', '->', '//', '--', '\\', '|', 'C:\\', 'D:\\']

        if keyword.lower() in partial_match_keywords:
            # Allow partial matches for these keywords
            return escaped_keyword
        elif keyword.lower() in wildcard_keywords:
            # Allow wildcard matching (e.g., "spawn" matches "spawns", "spawning", "spawned")
            return escaped_keyword + r'\w*'
        elif keyword in symbol_keywords:
            # For symbols, don't use word boundaries
            return escaped_keyword
        elif keyword.startswith('-') or keyword.endswith('-'):
            # For keywords with leading/trailing hyphens, use letter boundaries instead of word boundaries
            return r"(?<![a-zA-Z])" + escaped_keyword + r"(?![a-zA-Z])"
        elif keyword.endswith('.exe'):
            # For .exe executables, always require .exe extension to avoid false positives
            # with common English words (e.g., "services", "system", "process")
            base_name = keyword[:-4]  # Remove .exe
            # For short base names (2-3 chars), allow without extension if followed by non-word char
            # This handles cases like "cmd" in command lines, but prevents matches in words
            if len(base_name) <= 3:
                # Match: base.exe OR base followed by non-word char (space, punctuation, etc.)
                return r'\b' + re.escape(base_name) + r'(\.exe\b|(?![a-zA-Z0-9]))'
            else:
                # For longer names, require .exe extension to prevent false positives
                # with common words (e.g., "services" in "cloud services")
                return r'\b' + re.escape(base_name) + r'\.exe\b'
        elif keyword.endswith('.dll'):
            # For .dll files, match both with and without .dll extension
            base_name = keyword[:-4]  # Remove .dll
            # For short base names (2-3 chars), require either .dll extension or
            # ensure it's not part of a longer word by requiring non-word char after
            if len(base_name) <= 3:
                # Match: base.dll OR base followed by non-word char (space, punctuation, etc.)
                return r'\b' + re.escape(base_name) + r'(\.dll\b|(?![a-zA-Z0-9]))'
            else:
                # For longer names, use standard word boundary matching
                return r'\b' + re.escape(base_name) + r'(\.dll)?\b'
        elif ' ' in keyword:
            # For multi-word phrases, ensure word boundaries at start and end
            # but allow flexible matching in the middle
            return r'\b' + escaped_keyword + r'\b'
        else:
            # Use word boundaries for other keywords
            return r'\b' + escaped_keyword + r'\b'
