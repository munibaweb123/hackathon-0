"""Information retrieval system."""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from .entities import FileEntity
from .vault_manager import VaultManager
from .logger import Logger


class InformationIndex:
    """Index of information in the vault."""

    def __init__(self):
        self.index: Dict[str, Dict] = {}  # file_path -> metadata
        self.schema_definitions: Dict[str, List[str]] = {}  # schema_name -> fields
        self.tags_index: Dict[str, List[str]] = {}  # tag -> [file_paths]

    def add_file(self, file_path: str, content: str, metadata: Dict = None):
        """Add a file to the index."""
        if metadata is None:
            metadata = {}

        # Extract tags from content (simple hashtag detection)
        tags = re.findall(r'#(\w+)', content)

        # Extract basic metadata if not provided
        if not metadata:
            metadata = {
                "size": len(content),
                "word_count": len(content.split()),
                "created_at": datetime.now().isoformat(),
                "tags": tags
            }

        self.index[file_path] = metadata

        # Update tags index
        for tag in tags:
            if tag not in self.tags_index:
                self.tags_index[tag] = []
            if file_path not in self.tags_index[tag]:
                self.tags_index[tag].append(file_path)

    def remove_file(self, file_path: str):
        """Remove a file from the index."""
        if file_path in self.index:
            # Remove from tags index
            metadata = self.index[file_path]
            for tag in metadata.get("tags", []):
                if tag in self.tags_index and file_path in self.tags_index[tag]:
                    self.tags_index[tag].remove(file_path)

            del self.index[file_path]

    def search_by_content(self, query: str) -> List[Tuple[str, float]]:
        """Search for files by content, returning file paths with relevance scores."""
        results = []

        for file_path, metadata in self.index.items():
            content = metadata.get("content", "")

            # Simple relevance scoring based on term frequency
            query_lower = query.lower()
            content_lower = content.lower()

            # Count occurrences of query terms in content
            score = 0
            for term in query_lower.split():
                score += content_lower.count(term)

            # Boost score if terms appear close together
            if len(query_lower.split()) > 1:
                if query_lower in content_lower:
                    score *= 2

            if score > 0:
                results.append((file_path, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def search_by_tag(self, tag: str) -> List[str]:
        """Search for files by tag."""
        return self.tags_index.get(tag, [])

    def search_by_schema(self, schema_name: str) -> List[str]:
        """Search for files matching a specific schema."""
        matching_files = []

        for file_path, metadata in self.index.items():
            file_schema = metadata.get("schema", "")
            if file_schema == schema_name:
                matching_files.append(file_path)

        return matching_files

    def get_all_tags(self) -> List[str]:
        """Get all tags in the index."""
        return list(self.tags_index.keys())

    def get_statistics(self) -> Dict:
        """Get statistics about the index."""
        total_files = len(self.index)
        total_tags = len(self.tags_index)
        total_words = sum(metadata.get("word_count", 0) for metadata in self.index.values())

        return {
            "total_files": total_files,
            "total_tags": total_tags,
            "total_words": total_words,
            "avg_words_per_file": total_words / total_files if total_files > 0 else 0
        }


class InformationRetrieval:
    """Manages information retrieval within the vault."""

    def __init__(self, vault_manager: VaultManager, logger: Logger):
        self.vault_manager = vault_manager
        self.logger = logger
        self.index = InformationIndex()

    def _extract_content_from_file(self, file_path: Path) -> str:
        """Extract content from a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # If UTF-8 fails, try other encodings
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except:
                self.logger.error("info_retrieval", "file_read_error",
                                 f"Could not read file {file_path.name}")
                return ""
        except Exception as e:
            self.logger.error("info_retrieval", "file_read_error",
                             f"Error reading file {file_path.name}: {str(e)}")
            return ""

    def _is_sensitive_content(self, content: str) -> bool:
        """Check if content contains sensitive information."""
        sensitive_keywords = [
            'password', 'secret', 'private', 'confidential', 'ssn', 'social security',
            'credit card', 'bank account', 'api key', 'token', 'authorization'
        ]

        content_lower = content.lower()
        for keyword in sensitive_keywords:
            if keyword in content_lower:
                return True
        return False

    def index_file(self, file_path: Path) -> bool:
        """Index a file for information retrieval."""
        try:
            # Extract content
            content = self._extract_content_from_file(file_path)

            # Check for sensitive content
            is_sensitive = self._is_sensitive_content(content)

            # Prepare metadata
            metadata = {
                "path": str(file_path),
                "name": file_path.name,
                "size": len(content),
                "word_count": len(content.split()),
                "created_at": datetime.now().isoformat(),
                "content": content[:1000],  # Store first 1000 chars for search
                "is_sensitive": is_sensitive
            }

            # Add to index
            self.index.add_file(str(file_path), content, metadata)

            self.logger.audit("info_retrieval", "file_indexed",
                             f"Indexed file {file_path.name}",
                             file_ref=str(file_path))

            return True

        except Exception as e:
            self.logger.error("info_retrieval", "indexing_error",
                             f"Error indexing file {file_path.name}: {str(e)}")
            return False

    def index_folder(self, folder_name: str) -> int:
        """Index all files in a specific folder."""
        files = self.vault_manager.get_files_in_folder(folder_name)
        indexed_count = 0

        for file_path in files:
            if self.index_file(file_path):
                indexed_count += 1

        self.logger.info("info_retrieval", "folder_indexed",
                        f"Indexed {indexed_count} files in {folder_name} folder")

        return indexed_count

    def search(self, query: str, include_sensitive: bool = False) -> List[Dict]:
        """Search for information in the vault."""
        # Search by content
        content_results = self.index.search_by_content(query)

        # Search by tags
        tag_results = []
        if query.startswith('#'):
            tag = query[1:]  # Remove the # prefix
            tag_files = self.index.search_by_tag(tag)
            tag_results = [(path, 1.0) for path in tag_files]  # Give equal score to tag matches

        # Combine results
        all_results = content_results + tag_results

        # Remove duplicates, keeping highest score
        unique_results = {}
        for path, score in all_results:
            if path not in unique_results or unique_results[path] < score:
                unique_results[path] = score

        # Convert to list and sort
        sorted_results = sorted(unique_results.items(), key=lambda x: x[1], reverse=True)

        # Prepare results with file information
        result_list = []
        for path, score in sorted_results:
            metadata = self.index.index.get(path, {})

            # Skip sensitive files unless explicitly requested
            if not include_sensitive and metadata.get("is_sensitive", False):
                continue

            result_list.append({
                "file_path": path,
                "score": score,
                "name": metadata.get("name", ""),
                "size": metadata.get("size", 0),
                "word_count": metadata.get("word_count", 0),
                "is_sensitive": metadata.get("is_sensitive", False)
            })

        self.logger.audit("info_retrieval", "search_performed",
                         f"Search for '{query}' returned {len(result_list)} results")

        return result_list

    def get_tags(self) -> List[str]:
        """Get all tags in the vault."""
        tags = self.index.get_all_tags()
        self.logger.info("info_retrieval", "tags_retrieved",
                        f"Retrieved {len(tags)} tags")
        return tags

    def get_statistics(self) -> Dict:
        """Get statistics about the indexed information."""
        stats = self.index.get_statistics()
        self.logger.info("info_retrieval", "stats_retrieved",
                        f"Retrieved index statistics: {stats}")
        return stats

    def tag_file(self, file_path: Path, tags: List[str]) -> bool:
        """Add tags to a file."""
        file_str = str(file_path)
        if file_str not in self.index.index:
            self.logger.error("info_retrieval", "file_not_indexed",
                             f"Cannot tag file {file_path.name}, it's not indexed")
            return False

        # Update metadata with tags
        metadata = self.index.index[file_str]
        current_tags = metadata.get("tags", [])
        new_tags = list(set(current_tags + tags))  # Remove duplicates

        metadata["tags"] = new_tags
        self.index.index[file_str] = metadata

        # Update tags index
        for tag in tags:
            if tag not in self.index.tags_index:
                self.index.tags_index[tag] = []
            if file_str not in self.index.tags_index[tag]:
                self.index.tags_index[tag].append(file_str)

        self.logger.audit("info_retrieval", "file_tagged",
                         f"Tagged file {file_path.name} with {tags}",
                         file_ref=str(file_path))

        return True