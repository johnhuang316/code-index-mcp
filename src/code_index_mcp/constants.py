"""
Shared constants for the Code Index MCP server.
"""

# Directory and file names
SETTINGS_DIR = "code_indexer"
CONFIG_FILE = "config.json"
INDEX_FILE = "index.json"  # JSON index file (deep index)
INDEX_FILE_SHALLOW = "index.shallow.json"  # Minimal shallow index (file list)
INDEX_FILE_DB = "index.db"  # SQLite deep index file

# Supported file extensions for code analysis
# This is the authoritative list used by both old and new indexing systems
SUPPORTED_EXTENSIONS = [
    # Core programming languages
    '.py', '.pyw',                    # Python
    '.js', '.jsx', '.ts', '.tsx',     # JavaScript/TypeScript
    '.mjs', '.cjs',                   # Modern JavaScript
    '.java',                          # Java
    '.c', '.cpp', '.h', '.hpp',       # C/C++
    '.cxx', '.cc', '.hxx', '.hh',     # C++ variants
    '.cs',                            # C#
    '.go',                            # Go
    '.m', '.mm',                      # Objective-C
    '.rb',                            # Ruby
    '.php',                           # PHP
    '.swift',                         # Swift
    '.kt', '.kts',                    # Kotlin
    '.rs',                            # Rust
    '.scala',                         # Scala
    '.sh', '.bash', '.zsh',           # Shell scripts
    '.ps1',                           # PowerShell
    '.bat', '.cmd',                   # Windows batch
    '.r', '.R',                       # R
    '.pl', '.pm',                     # Perl
    '.lua',                           # Lua
    '.dart',                          # Dart
    '.hs',                            # Haskell
    '.ml', '.mli',                    # OCaml
    '.fs', '.fsx',                    # F#
    '.clj', '.cljs',                  # Clojure
    '.vim',                           # Vim script
    '.zig', '.zon',                   # Zig

    # Web and markup
    '.html', '.htm',                  # HTML
    '.css', '.scss', '.sass',         # Stylesheets
    '.less', '.stylus', '.styl',      # Style languages
    '.md', '.mdx',                    # Markdown
    '.json', '.jsonc',                # JSON
    '.xml',                           # XML
    '.yml', '.yaml',                  # YAML

    # Frontend frameworks
    '.vue',                           # Vue.js
    '.svelte',                        # Svelte
    '.astro',                         # Astro

    # Java web & build artifacts
    '.jsp', '.jspx', '.jspf',         # JSP pages
    '.tag', '.tagx',                  # JSP tag files
    '.gsp',                           # Grails templates
    '.properties',                    # Java .properties configs
    '.gradle', '.groovy',             # Gradle/Groovy build scripts
    '.proto',                         # Protocol Buffers

    # Template engines
    '.hbs', '.handlebars',            # Handlebars
    '.ejs',                           # EJS
    '.pug',                           # Pug
    '.ftl',                           # FreeMarker
    '.mustache', '.liquid', '.erb',   # Additional template engines

    # Database and SQL
    '.sql', '.ddl', '.dml',           # SQL
    '.mysql', '.postgresql', '.psql', # Database-specific SQL
    '.sqlite', '.mssql', '.oracle',   # More databases
    '.ora', '.db2',                   # Oracle and DB2
    '.proc', '.procedure',            # Stored procedures
    '.func', '.function',             # Functions
    '.view', '.trigger', '.index',    # Database objects
    '.migration', '.seed', '.fixture', # Migration files
    '.schema',                        # Schema files
    '.cql', '.cypher', '.sparql',     # NoSQL query languages
    '.gql',                           # GraphQL
    '.liquibase', '.flyway',          # Migration tools
]

# Centralized filtering configuration
FILTER_CONFIG = {
    "exclude_directories": {
        # Version control
        '.git', '.svn', '.hg', '.bzr',
        
        # Package managers & dependencies  
        'node_modules', '__pycache__', '.venv', 'venv',
        'vendor', 'bower_components',
        
        # Build outputs
        'dist', 'build', 'target', 'out', 'bin', 'obj',
        
        # IDE & editors
        '.idea', '.vscode', '.vs', '.sublime-workspace',
        
        # Testing & coverage
        '.pytest_cache', '.coverage', '.tox', '.nyc_output',
        'coverage', 'htmlcov',
        
        # OS artifacts
        '.DS_Store', 'Thumbs.db', 'desktop.ini'
    },
    
    "exclude_files": {
        # Temporary files
        '*.tmp', '*.temp', '*.swp', '*.swo',
        
        # Backup files  
        '*.bak', '*~', '*.orig',
        
        # Log files
        '*.log',
        
        # Lock files
        'package-lock.json', 'yarn.lock', 'Pipfile.lock'
    },
    
    "supported_extensions": SUPPORTED_EXTENSIONS
}
