# Warning

This project is a one-shot migration tool. It is not actively maintained. The testing and validation is limited to 
whatever features were needed for a pro bono project.

It was 100% written by Claude Code using the Opus 4.1 model.

# Papers3 to Zotero Migration Tool

A Python tool to migrate your Papers3 library directly to Zotero's SQLite database, preserving collections, PDFs, tags, and metadata.

## Features

-  Preserves complete collection hierarchy
-  Maintains PDF attachments as linked files (no duplication)
-  Keeps all authors with correct ordering and roles
-  Preserves tags/keywords
-  Stores Papers3-specific metadata (ratings, read status) in Extra field
-  Maps Papers3 publication types to appropriate Zotero types
-  Handles bundle relationships (journal-article connections)
-  Transaction-based import with rollback on error

## Prerequisites

1. **Papers3 Export**: Run the Papers3 extraction scripts to generate JSON files:
   ```bash
   python papers3_scripts/papers3_publications.py --full
   python papers3_scripts/papers3_collections.py
   python papers3_scripts/papers3_authors.py
   python papers3_scripts/papers3_pdfs.py
   ```

2. **Zotero Database**: 
   - Install Zotero desktop application
   - Create a backup of your Zotero database (usually at `~/Zotero/zotero.sqlite`)
   - For testing, use a fresh Zotero installation or copy of the database

## Installation

```bash
# Clone the repository
git clone <repository>
cd papers3-zotero

# Install with uv
uv sync

# Or install with pip
pip install -e .
```

## Usage

### Test Mode (Recommended First)

Test with a small subset without making permanent changes:

```bash
uv run python papers3_to_zotero.py \
  --json-catalog ./catalog \
  --files-dir ~/Papers3/Library/Files \
  --files-target-dir ~/Documents/ZoteroLibrary \
  --zotero-db zotero.sqlite \
  --test \
  --limit 10
```

### Full Migration with File Organization

After successful test, run the full migration with file copying:

```bash
uv run python papers3_to_zotero.py \
  --json-catalog ./catalog \
  --files-dir ~/Papers3/Library/Files \
  --files-target-dir ~/Documents/ZoteroLibrary \
  --zotero-db ~/Zotero/zotero.sqlite
```

### Files-Only Mode

Organize files without touching the database:

```bash
uv run python papers3_to_zotero.py \
  --json-catalog ./catalog \
  --files-dir ~/Papers3/Library/Files \
  --files-target-dir ~/Documents/ZoteroLibrary \
  --zotero-db ~/Zotero/zotero.sqlite \
  --files-only
```

### Command Line Options

**Required Arguments:**
- `--json-catalog`: Path to Papers3 JSON catalog directory containing exported files
- `--files-dir`: Path to Papers3 Files directory with hex subdirectories (00-FF)
- `--files-target-dir`: Destination directory for organized files

**Optional Arguments:**
- `--zotero-db`: Path to Zotero SQLite database (default: `zotero.sqlite`)
- `--test`: Run in test mode - simulates operations without making changes
- `--limit N`: Import only first N items (useful for testing)
- `--files-only`: Only copy/organize files, skip database migration
- `--skip-attachments`: Skip all attachment processing (metadata only)

## Migration Mapping

### Item Types

| Papers3 Type | Zotero Type      |
|--------------|------------------|
| Article      | Journal Article  |
| Book         | Book             |
| Book Chapter | Book Section     |
| Report       | Report           |
| Thesis       | Thesis           |
| Patent       | Patent           |
| Conference   | Conference Paper |
| Website      | Web Page         |
| Media        | Document         |

### Preserved Metadata

- Title, subtitle, abstract
- Authors, editors, translators with correct order
- DOI, ISBN, ISSN
- Publication date
- Journal name, volume, issue, pages
- Publisher, place
- URL
- Language
- Keywords � Tags
- Collections � Folders

### Papers3-Specific Data

Stored in Zotero's Extra field:
- Star rating (1-5)
- Read status
- Times cited
- Original Papers3 UUID

### PDF Attachments

The tool offers two approaches for handling attachments:

**1. File Organization (Recommended)**
- Copies PDFs from Papers3's hex-based structure to human-readable folders
- Organizes as: `Year/Author_Lastname/Title_Year.pdf`
- Stores absolute paths to new locations in Zotero database
- Preserves original files as backup

**2. Link-Only Mode** (use `--skip-attachments` flag)
- Skips all attachment processing
- Imports only bibliographic metadata
- Useful for quick metadata-only imports

**File Organization Features:**
- Sanitizes filenames for cross-platform compatibility
- Smart collision handling with content-based duplicate detection
- Properly resumes interrupted migrations (uses MD5 hashing)
- Handles name collisions by appending _2, _3, etc.
- Logs missing files for review
- Works in test mode to preview changes

## Important Notes

1. **Backup First**: Always backup your Zotero database before migration
2. **Close Zotero**: Ensure Zotero is closed during migration
3. **Files Directory**: The `--files-dir` should point to Papers3's Files folder containing hex subdirectories (00, 01, ... FF)
4. **File Organization**: Files are copied to a new structure, preserving originals
5. **Duplicates**: The script doesn't check for existing items - run on clean database or handle duplicates after
6. **Sync**: After migration, Zotero will sync the new items to your online library (if configured)

## Troubleshooting

### Common Issues

1. **"Database is locked"**: Close Zotero application first
2. **Foreign key constraint errors**: Usually indicates corrupted data - check error logs
3. **Missing PDFs**: Verify PDF paths in Papers3 export are correct
4. **Memory issues with large libraries**: Process in batches using `--limit`

### Verification Steps

After migration:
1. Open Zotero and check library loads correctly
2. Verify collection hierarchy matches Papers3
3. Test opening several PDFs
4. Check author names and ordering
5. Verify tags were imported
6. Search for items to test indexing

## Data Structure

The tool expects the following structure:

### Required Files
```
catalog/                              # JSON catalog directory
├── papers3_publications_full.json   # Main publication data (or papers3_publications.json)
└── papers3_collections.json         # Collection hierarchy (optional)

Files/                               # Papers3 Files directory
├── 00/                             # Hex-based subdirectories
│   └── UUID.pdf                    # Attachment files
├── 01/
├── ...
└── FF/
```

### Output Structure
```
ZoteroLibrary/                      # Target directory for organized files
├── 2023/                          # Year directories
│   ├── Smith/                     # Author last name
│   │   ├── Paper_Title_2023.pdf
│   │   └── Another_Paper_2023.pdf
│   └── Johnson/
│       └── Research_Study_2023.pdf
└── Unknown/                       # For items without dates
    └── NoAuthor/                  # For items without authors
```

## Limitations

### Not Preserved
- Change history/sync data
- UI preferences
- Saved searches
- Duplicate detection (all items imported as new)

### Partially Preserved
- Ratings (as text in Extra field)
- Read status (as text in Extra field)
- Bundle relationships (as publication info)

## Migration Statistics

After migration, the tool reports:
- Collections imported
- Items imported  
- Attachments linked
- Files copied/organized
- Files skipped (already exist)
- Missing files (logged to `migration_missing_files.log`)

## Contributing

Issues and pull requests welcome! Areas for improvement:
- Better duplicate detection
- Option to import PDFs into Zotero storage (instead of linking)
- Progress bar for large libraries
- Parallel file copying for performance
- Validation of Papers3 data before import

## License

MIT License - See LICENSE file for details

Note: The scripts in `papers3_scripts/` are vendored/included under a research license - see `papers3_scripts/README.md` for their specific licensing terms.