"""Content Chunking Service for ML Pipeline

Splits articles into analyzable chunks for ML classification.
Chunks are designed to be:
- Self-contained enough for classification
- Small enough for efficient processing
- Overlapping to avoid boundary issues
"""
import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a content chunk for ML processing"""
    index: int
    text: str
    start_position: int
    end_position: int
    word_count: int
    sentence_count: int

    # Optional metadata
    contains_code: bool = False
    contains_command: bool = False
    contains_ioc: bool = False


class ContentChunker:
    """Splits article content into chunks for ML classification.

    Strategy:
    - Target chunk size: 200-500 words (optimal for classification)
    - Split on paragraph boundaries when possible
    - Preserve code blocks as single chunks
    - Add overlap between chunks to avoid boundary issues
    """

    # Patterns for detecting technical content
    CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```|`[^`]+`')
    COMMAND_PATTERN = re.compile(
        r'(\$\s*[\w\-./]+|'  # Shell commands starting with $
        r'>\s*[\w\-./]+|'  # PowerShell/CMD prompts
        r'\b(cmd|powershell|bash|sh)\s+[\-/]|'  # Shell invocations
        r'\\\\[\w\-.]+\\|'  # UNC paths
        r'[A-Z]:\\[\w\-./\\]+)',  # Windows paths
        re.IGNORECASE
    )
    IOC_PATTERN = re.compile(
        r'(\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|'  # IP addresses
        r'\b[a-fA-F0-9]{32}\b|'  # MD5
        r'\b[a-fA-F0-9]{40}\b|'  # SHA1
        r'\b[a-fA-F0-9]{64}\b|'  # SHA256
        r'hxxp[s]?://|'  # Defanged URLs
        r'\b[\w\-]+\[?\.\]?(?:com|net|org|io|ru|cn)\b)'  # Domains
    )

    def __init__(
        self,
        min_chunk_words: int = 150,
        target_chunk_words: int = 300,
        max_chunk_words: int = 500,
        overlap_sentences: int = 1
    ):
        """
        Initialize the chunker.

        Args:
            min_chunk_words: Minimum words per chunk (except last chunk)
            target_chunk_words: Target words per chunk
            max_chunk_words: Maximum words before forcing a split
            overlap_sentences: Number of sentences to overlap between chunks
        """
        self.min_chunk_words = min_chunk_words
        self.target_chunk_words = target_chunk_words
        self.max_chunk_words = max_chunk_words
        self.overlap_sentences = overlap_sentences

    def chunk_article(self, content: str, title: str = "") -> List[Chunk]:
        """
        Split article content into chunks for ML processing.

        Args:
            content: Full article content
            title: Article title (prepended to first chunk)

        Returns:
            List of Chunk objects
        """
        if not content or not content.strip():
            return []

        # Normalize whitespace
        content = self._normalize_text(content)

        # Extract and preserve code blocks
        code_blocks, content_with_placeholders = self._extract_code_blocks(content)

        # Split into paragraphs
        paragraphs = self._split_paragraphs(content_with_placeholders)

        # Build chunks from paragraphs
        chunks = self._build_chunks(paragraphs, title)

        # Restore code blocks
        chunks = self._restore_code_blocks(chunks, code_blocks)

        # Detect technical content in each chunk
        for chunk in chunks:
            chunk.contains_code = bool(self.CODE_BLOCK_PATTERN.search(chunk.text))
            chunk.contains_command = bool(self.COMMAND_PATTERN.search(chunk.text))
            chunk.contains_ioc = bool(self.IOC_PATTERN.search(chunk.text))

        logger.debug(f"Created {len(chunks)} chunks from content ({len(content)} chars)")
        return chunks

    def _normalize_text(self, text: str) -> str:
        """Normalize whitespace and clean text."""
        # Replace multiple newlines with double newline (paragraph separator)
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Replace multiple spaces with single space
        text = re.sub(r' {2,}', ' ', text)
        # Strip leading/trailing whitespace
        return text.strip()

    def _extract_code_blocks(self, text: str) -> Tuple[List[str], str]:
        """Extract code blocks and replace with placeholders."""
        code_blocks = []

        def replace_code(match):
            code_blocks.append(match.group(0))
            return f"[[CODE_BLOCK_{len(code_blocks) - 1}]]"

        text_with_placeholders = self.CODE_BLOCK_PATTERN.sub(replace_code, text)
        return code_blocks, text_with_placeholders

    def _restore_code_blocks(self, chunks: List[Chunk], code_blocks: List[str]) -> List[Chunk]:
        """Restore code blocks from placeholders."""
        for chunk in chunks:
            for i, code_block in enumerate(code_blocks):
                placeholder = f"[[CODE_BLOCK_{i}]]"
                chunk.text = chunk.text.replace(placeholder, code_block)
        return chunks

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        paragraphs = text.split('\n\n')
        # Filter out empty paragraphs
        return [p.strip() for p in paragraphs if p.strip()]

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting - handles common cases
        # Avoid splitting on abbreviations and decimals
        sentence_pattern = re.compile(
            r'(?<=[.!?])\s+(?=[A-Z])|'  # Standard sentence boundaries
            r'(?<=[.!?])\s*\n'  # Sentence ending at newline
        )
        sentences = sentence_pattern.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def _count_words(self, text: str) -> int:
        """Count words in text."""
        return len(text.split())

    def _build_chunks(self, paragraphs: List[str], title: str = "") -> List[Chunk]:
        """Build chunks from paragraphs."""
        chunks = []
        current_text = ""
        current_start = 0
        position = 0

        # Add title to first chunk if provided
        if title:
            current_text = f"{title}\n\n"
            position = len(current_text)

        for paragraph in paragraphs:
            paragraph_words = self._count_words(paragraph)
            current_words = self._count_words(current_text)

            # Check if adding this paragraph would exceed max
            if current_words + paragraph_words > self.max_chunk_words and current_text:
                # Save current chunk
                chunk = self._create_chunk(
                    index=len(chunks),
                    text=current_text,
                    start_position=current_start
                )
                chunks.append(chunk)

                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_text)
                current_text = overlap_text + paragraph + "\n\n"
                current_start = position - len(overlap_text)
            else:
                current_text += paragraph + "\n\n"

            position += len(paragraph) + 2  # +2 for \n\n

            # Check if we've reached target size and paragraph is a good break point
            current_words = self._count_words(current_text)
            if current_words >= self.target_chunk_words:
                # Save chunk if we have enough content
                if current_words >= self.min_chunk_words:
                    chunk = self._create_chunk(
                        index=len(chunks),
                        text=current_text,
                        start_position=current_start
                    )
                    chunks.append(chunk)

                    # Start new chunk with overlap
                    overlap_text = self._get_overlap_text(current_text)
                    current_text = overlap_text
                    current_start = position - len(overlap_text)

        # Add final chunk if there's remaining content
        if current_text.strip():
            chunk = self._create_chunk(
                index=len(chunks),
                text=current_text,
                start_position=current_start
            )
            chunks.append(chunk)

        return chunks

    def _get_overlap_text(self, text: str) -> str:
        """Get overlap text (last N sentences) for chunk continuity."""
        if self.overlap_sentences <= 0:
            return ""

        sentences = self._split_sentences(text)
        if len(sentences) <= self.overlap_sentences:
            return ""

        overlap_sentences = sentences[-self.overlap_sentences:]
        return " ".join(overlap_sentences) + " "

    def _create_chunk(self, index: int, text: str, start_position: int) -> Chunk:
        """Create a Chunk object."""
        text = text.strip()
        sentences = self._split_sentences(text)

        return Chunk(
            index=index,
            text=text,
            start_position=start_position,
            end_position=start_position + len(text),
            word_count=self._count_words(text),
            sentence_count=len(sentences)
        )

    def chunk_for_annotation(
        self,
        content: str,
        window_size: int = 500,
        step_size: int = 250
    ) -> List[Chunk]:
        """
        Create overlapping chunks for annotation interface.

        Uses sliding window approach for more granular annotation.

        Args:
            content: Full article content
            window_size: Window size in characters
            step_size: Step size between windows

        Returns:
            List of overlapping Chunk objects
        """
        if not content or not content.strip():
            return []

        content = self._normalize_text(content)
        chunks = []

        position = 0
        index = 0

        while position < len(content):
            end_position = min(position + window_size, len(content))

            # Try to end at word boundary
            if end_position < len(content):
                # Find last space before end_position
                last_space = content.rfind(' ', position, end_position)
                if last_space > position:
                    end_position = last_space

            chunk_text = content[position:end_position].strip()

            if chunk_text:
                chunk = Chunk(
                    index=index,
                    text=chunk_text,
                    start_position=position,
                    end_position=end_position,
                    word_count=self._count_words(chunk_text),
                    sentence_count=len(self._split_sentences(chunk_text)),
                    contains_code=bool(self.CODE_BLOCK_PATTERN.search(chunk_text)),
                    contains_command=bool(self.COMMAND_PATTERN.search(chunk_text)),
                    contains_ioc=bool(self.IOC_PATTERN.search(chunk_text))
                )
                chunks.append(chunk)
                index += 1

            position += step_size

        return chunks
