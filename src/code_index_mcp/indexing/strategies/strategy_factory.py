"""
Strategy factory for creating appropriate parsing strategies.
"""

import threading
from typing import Dict, List
from .base_strategy import ParsingStrategy
from .python_strategy import PythonParsingStrategy
from .javascript_strategy import JavaScriptParsingStrategy
from .typescript_strategy import TypeScriptParsingStrategy
from .java_strategy import JavaParsingStrategy
from .kotlin_strategy import KotlinParsingStrategy
from .csharp_strategy import CSharpParsingStrategy
from .go_strategy import GoParsingStrategy
from .objective_c_strategy import ObjectiveCParsingStrategy
from .zig_strategy import ZigParsingStrategy
from .fallback_strategy import FallbackParsingStrategy


class StrategyFactory:
    """Factory for creating appropriate parsing strategies."""

    def __init__(self):
        # Initialize all strategies with thread safety
        self._strategies: Dict[str, ParsingStrategy] = {}
        self._initialized = False
        self._lock = threading.RLock()
        self._initialize_strategies()

        # File type mappings for fallback parser
        self._file_type_mappings = {
            # Web and markup
            '.html': 'html', '.htm': 'html',
            '.css': 'css', '.scss': 'css', '.sass': 'css',
            '.less': 'css', '.stylus': 'css', '.styl': 'css',
            '.md': 'markdown', '.mdx': 'markdown',
            '.json': 'json', '.jsonc': 'json',
            '.xml': 'xml',
            '.yml': 'yaml', '.yaml': 'yaml',

            # Frontend frameworks
            '.vue': 'vue',
            '.svelte': 'svelte',
            '.astro': 'astro',

            # Template engines
            '.hbs': 'handlebars', '.handlebars': 'handlebars',
            '.ejs': 'ejs',
            '.pug': 'pug',

            # Database and SQL
            '.sql': 'sql', '.ddl': 'sql', '.dml': 'sql',
            '.mysql': 'sql', '.postgresql': 'sql', '.psql': 'sql',
            '.sqlite': 'sql', '.mssql': 'sql', '.oracle': 'sql',
            '.ora': 'sql', '.db2': 'sql',
            '.proc': 'sql', '.procedure': 'sql',
            '.func': 'sql', '.function': 'sql',
            '.view': 'sql', '.trigger': 'sql', '.index': 'sql',
            '.migration': 'sql', '.seed': 'sql', '.fixture': 'sql',
            '.schema': 'sql',
            '.cql': 'sql', '.cypher': 'sql', '.sparql': 'sql',
            '.gql': 'graphql',
            '.liquibase': 'sql', '.flyway': 'sql',

            # Config and text files
            '.txt': 'text',
            '.ini': 'config', '.cfg': 'config', '.conf': 'config',
            '.toml': 'config',
            '.properties': 'config',
            '.env': 'config',
            '.gitignore': 'config',
            '.dockerignore': 'config',
            '.editorconfig': 'config',

            # Other programming languages (will use fallback)
            '.c': 'c', '.cpp': 'cpp', '.h': 'h', '.hpp': 'hpp',
            '.cxx': 'cpp', '.cc': 'cpp', '.hxx': 'hpp', '.hh': 'hpp',
            '.cs': 'csharp',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin', '.kts': 'kotlin',
            '.rs': 'rust',
            '.scala': 'scala',
            '.sh': 'shell', '.bash': 'shell', '.zsh': 'shell',
            '.ps1': 'powershell',
            '.bat': 'batch', '.cmd': 'batch',
            '.r': 'r', '.R': 'r',
            '.pl': 'perl', '.pm': 'perl',
            '.lua': 'lua',
            '.dart': 'dart',
            '.hs': 'haskell',
            '.ml': 'ocaml', '.mli': 'ocaml',
            '.fs': 'fsharp', '.fsx': 'fsharp',
            '.clj': 'clojure', '.cljs': 'clojure',
            '.vim': 'vim',
        }

    def _initialize_strategies(self):
        """Initialize all parsing strategies with thread safety."""
        with self._lock:
            if self._initialized:
                return
                
            try:
                # Python
                python_strategy = PythonParsingStrategy()
                for ext in python_strategy.get_supported_extensions():
                    self._strategies[ext] = python_strategy

                # JavaScript
                js_strategy = JavaScriptParsingStrategy()
                for ext in js_strategy.get_supported_extensions():
                    self._strategies[ext] = js_strategy

                # TypeScript
                ts_strategy = TypeScriptParsingStrategy()
                for ext in ts_strategy.get_supported_extensions():
                    self._strategies[ext] = ts_strategy

                # Java
                java_strategy = JavaParsingStrategy()
                for ext in java_strategy.get_supported_extensions():
                    self._strategies[ext] = java_strategy

                # Kotlin
                kotlin_strategy = KotlinParsingStrategy()
                for ext in kotlin_strategy.get_supported_extensions():
                    self._strategies[ext] = kotlin_strategy

                # C#
                csharp_strategy = CSharpParsingStrategy()
                for ext in csharp_strategy.get_supported_extensions():
                    self._strategies[ext] = csharp_strategy
                # Go
                go_strategy = GoParsingStrategy()
                for ext in go_strategy.get_supported_extensions():
                    self._strategies[ext] = go_strategy

                # Objective-C
                objc_strategy = ObjectiveCParsingStrategy()
                for ext in objc_strategy.get_supported_extensions():
                    self._strategies[ext] = objc_strategy

                # Zig
                zig_strategy = ZigParsingStrategy()
                for ext in zig_strategy.get_supported_extensions():
                    self._strategies[ext] = zig_strategy
                    
                self._initialized = True
                
            except Exception as e:
                # Reset state on failure to allow retry
                self._strategies.clear()
                self._initialized = False
                raise e

    def get_strategy(self, file_extension: str) -> ParsingStrategy:
        """
        Get appropriate strategy for file extension.

        Args:
            file_extension: File extension (e.g., '.py', '.js')

        Returns:
            Appropriate parsing strategy
        """
        with self._lock:
            # Ensure initialization is complete
            if not self._initialized:
                self._initialize_strategies()
            
            # Check for specialized strategies first
            if file_extension in self._strategies:
                return self._strategies[file_extension]

            # Use fallback strategy with appropriate language name
            language_name = self._file_type_mappings.get(file_extension, 'unknown')
            return FallbackParsingStrategy(language_name)

    def get_all_supported_extensions(self) -> List[str]:
        """Get all supported extensions across strategies."""
        specialized = list(self._strategies.keys())
        fallback = list(self._file_type_mappings.keys())
        return specialized + fallback

    def get_specialized_extensions(self) -> List[str]:
        """Get extensions that have specialized parsers."""
        return list(self._strategies.keys())

    def get_fallback_extensions(self) -> List[str]:
        """Get extensions that use fallback parsing."""
        return list(self._file_type_mappings.keys())

    def get_strategy_info(self) -> Dict[str, List[str]]:
        """Get information about available strategies."""
        info = {}

        # Group extensions by strategy type
        for ext, strategy in self._strategies.items():
            strategy_name = strategy.get_language_name()
            if strategy_name not in info:
                info[strategy_name] = []
            info[strategy_name].append(ext)

        # Add fallback info
        fallback_languages = set(self._file_type_mappings.values())
        for lang in fallback_languages:
            extensions = [ext for ext, mapped_lang in self._file_type_mappings.items() if mapped_lang == lang]
            info[f"fallback_{lang}"] = extensions

        return info
