"""Document classifier for file types."""

from pathlib import Path
from typing import Dict, List
import mimetypes


class DocumentClassifier:
    """Classifies documents based on file type and content."""

    def __init__(self):
        # Define file type categories
        self.file_types = {
            'text': ['.txt', '.md', '.rst', '.csv'],
            'document': ['.pdf', '.doc', '.docx', '.odt'],
            'spreadsheet': ['.xls', '.xlsx', '.ods', '.csv'],
            'code': ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.html', '.css', '.json', '.yaml', '.yml'],
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg'],
            'data': ['.json', '.xml', '.yaml', '.yml', '.csv']
        }

    def classify_file(self, file_path: Path) -> str:
        """Classify a file based on its extension and other characteristics."""
        # Get the file extension
        extension = file_path.suffix.lower()

        # Classify based on extension
        for category, extensions in self.file_types.items():
            if extension in extensions:
                return category

        # If extension doesn't match, try to guess from content
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            if mime_type.startswith('text/'):
                return 'text'
            elif mime_type.startswith('image/'):
                return 'image'
            elif 'pdf' in mime_type:
                return 'document'

        # Default to 'general' if no classification is found
        return 'general'

    def get_processing_recommendation(self, file_path: Path) -> str:
        """Get a recommended processing type based on file classification."""
        classification = self.classify_file(file_path)

        recommendations = {
            'text': 'analyze',
            'document': 'summarize',
            'spreadsheet': 'analyze',
            'code': 'analyze',
            'data': 'analyze',
            'image': 'categorize',  # Images can't be processed the same way as text
            'general': 'analyze'
        }

        return recommendations.get(classification, 'analyze')

    def is_processable(self, file_path: Path) -> bool:
        """Check if a file is processable by our system."""
        classification = self.classify_file(file_path)

        # For Bronze Tier, we only process text-based files
        processable_types = ['text', 'document', 'code', 'data']
        return classification in processable_types