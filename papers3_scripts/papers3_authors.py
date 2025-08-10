#!/usr/bin/env python3
"""
Papers3 Authors Extractor

This script extracts all authors from a Papers3 database
and generates a JSON representation with metadata.

Usage:
    python papers3_authors.py [database_path] [--full] [--human-readable] [--include-all]
    
Default database path: Database.papersdb
--full: Export full publication details instead of just UUIDs
--human-readable: Use first 75 characters of title instead of UUIDs
--include-all: Include all authors (default: only authors with publications)
"""

import sqlite3
import json
import sys
import os
from typing import Dict, List, Any, Optional
from datetime import datetime


class Papers3AuthorsExtractor:
    def __init__(self, database_path: str = "Database.papersdb", full_export: bool = False, human_readable: bool = False, include_all: bool = False):
        self.database_path = database_path
        self.full_export = full_export
        self.human_readable = human_readable
        self.include_all = include_all
        self.authors = {}
        self.author_publications = {}
        
    def connect_database(self) -> sqlite3.Connection:
        """Connect to the Papers3 SQLite database."""
        if not os.path.exists(self.database_path):
            raise FileNotFoundError(f"Database file not found: {self.database_path}")
        
        return sqlite3.connect(self.database_path)
    
    def _convert_author_type(self, type_value: Optional[int]) -> Optional[str]:
        """Convert author type integer to lowercase name.
        
        Mapping based on PredicateEditor.plist:
        - 0: author
        - 1: editor
        - 2: photographer  
        - 3: translator
        """
        if type_value is None:
            return None
            
        type_mapping = {
            0: "author",
            1: "editor", 
            2: "photographer",
            3: "translator"
        }
        
        return type_mapping.get(type_value, f"unknown_{type_value}")
    
    def get_authors(self, conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
        """Extract all authors with their metadata."""
        cursor = conn.cursor()
        
        query = """
        SELECT 
            uuid,
            fullname,
            prename,
            surname,
            initial,
            standard_name,
            nickname,
            email,
            affiliation,
            location,
            post_title,
            pre_title,
            notes,
            institutional,
            is_me,
            flagged,
            publication_count,
            type,
            created_at,
            updated_at
        FROM Author
        ORDER BY fullname
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        authors = {}
        for row in rows:
            author = {
                "uuid": row[0],
                "fullname": row[1],
                "prename": row[2],
                "surname": row[3],
                "initial": row[4],
                "standard_name": row[5],
                "nickname": row[6],
                "email": row[7],
                "affiliation": row[8],
                "location": row[9],
                "post_title": row[10],
                "pre_title": row[11],
                "notes": row[12],
                "institutional": bool(row[13]) if row[13] is not None else None,
                "is_me": bool(row[14]) if row[14] is not None else None,
                "flagged": bool(row[15]) if row[15] is not None else None,
                "publication_count": row[16],
                "type": self._convert_author_type(row[17]),
                "created_at": self._format_timestamp(row[18]),
                "updated_at": self._format_timestamp(row[19]),
                "publications": []
            }
            authors[row[0]] = author
            
        return authors
    
    def get_author_publications(self, conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
        """Extract all publications for each author."""
        cursor = conn.cursor()
        
        if self.full_export:
            # Full export with all publication details
            query = """
            SELECT 
                oa.author_id,
                oa.object_id,
                oa.priority,
                oa.type,
                oa.created_at,
                oa.updated_at,
                p.title,
                p.author_string,
                p.publication_date,
                p.doi,
                p.publisher,
                p.volume,
                p.startpage,
                p.endpage,
                p.type as pub_type,
                p.rating,
                p.read_status,
                p.flagged,
                p.notes,
                p.keyword_string,
                p.times_cited,
                p.times_read
            FROM OrderedAuthor oa
            JOIN Publication p ON oa.object_id = p.uuid
            ORDER BY oa.author_id, oa.priority, p.title
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            author_publications = {}
            for row in rows:
                item = {
                    "publication_uuid": row[1],
                    "priority": row[2],
                    "type": self._convert_author_type(row[3]),
                    "created_at": self._format_timestamp(row[4]),
                    "updated_at": self._format_timestamp(row[5]),
                    "title": row[6],
                    "author_string": row[7],
                    "publication_date": row[8],
                    "doi": row[9],
                    "publisher": row[10],
                    "volume": row[11],
                    "startpage": row[12],
                    "endpage": row[13],
                    "pages": f"{row[12]}-{row[13]}" if row[12] and row[13] else None,
                    "publication_type": row[14],
                    "rating": row[15],
                    "read_status": row[16],
                    "flagged": bool(row[17]) if row[17] is not None else False,
                    "notes": row[18],
                    "keyword_string": row[19],
                    "times_cited": row[20],
                    "times_read": row[21]
                }
                
                author_uuid = row[0]
                if author_uuid not in author_publications:
                    author_publications[author_uuid] = []
                author_publications[author_uuid].append(item)
        else:
            # Lightweight export with UUIDs and optionally titles
            if self.human_readable:
                query = """
                SELECT 
                    oa.author_id,
                    oa.object_id,
                    oa.priority,
                    p.title
                FROM OrderedAuthor oa
                JOIN Publication p ON oa.object_id = p.uuid
                ORDER BY oa.author_id, oa.priority
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                author_publications = {}
                for row in rows:
                    title = row[3] if row[3] else "Untitled"
                    title_preview = title[:75] + "..." if len(title) > 75 else title
                    
                    item = {
                        "publication_uuid": row[1],
                        "title_preview": title_preview,
                        "priority": row[2]
                    }
                    
                    author_uuid = row[0]
                    if author_uuid not in author_publications:
                        author_publications[author_uuid] = []
                    author_publications[author_uuid].append(item)
            else:
                query = """
                SELECT 
                    oa.author_id,
                    oa.object_id,
                    oa.priority
                FROM OrderedAuthor oa
                ORDER BY oa.author_id, oa.priority
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                author_publications = {}
                for row in rows:
                    item = {
                        "publication_uuid": row[1],
                        "priority": row[2]
                    }
                    
                    author_uuid = row[0]
                    if author_uuid not in author_publications:
                        author_publications[author_uuid] = []
                    author_publications[author_uuid].append(item)
            
        return author_publications
    
    def build_authors_with_publications(self, authors: Dict[str, Dict[str, Any]], 
                                      author_publications: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Build the authors list with their publications."""
        # Add publications to authors
        for author_uuid, publications in author_publications.items():
            if author_uuid in authors:
                if self.full_export:
                    authors[author_uuid]["publications"] = publications
                else:
                    if self.human_readable:
                        # For human-readable export, store title previews
                        authors[author_uuid]["publications"] = [pub["title_preview"] for pub in publications]
                    else:
                        # For lightweight export, just store the UUIDs
                        authors[author_uuid]["publications"] = [pub["publication_uuid"] for pub in publications]
                authors[author_uuid]["publication_count"] = len(publications)
        
        # Filter authors based on include_all parameter
        if not self.include_all:
            # Only include authors with publications
            authors_list = [author for author in authors.values() if author.get("publications")]
        else:
            # Include all authors
            authors_list = list(authors.values())
        
        # Sort by fullname
        authors_list.sort(key=lambda x: (x.get("fullname", ""), x.get("surname", ""), x.get("prename", "")))
        
        return authors_list
    
    def get_author_statistics(self, authors: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Generate statistics about the authors."""
        total_authors = len(authors)
        
        if self.full_export:
            total_publications = sum(len(a.get("publications", [])) for a in authors.values())
            authors_with_publications = sum(1 for a in authors.values() if a.get("publications"))
        else:
            total_publications = sum(len(a.get("publications", [])) for a in authors.values())
            authors_with_publications = sum(1 for a in authors.values() if a.get("publications"))
        
        authors_with_affiliation = sum(1 for a in authors.values() if a.get("affiliation"))
        authors_with_email = sum(1 for a in authors.values() if a.get("email"))
        institutional_authors = sum(1 for a in authors.values() if a.get("institutional"))
        flagged_authors = sum(1 for a in authors.values() if a.get("flagged"))
        
        return {
            "total_authors": total_authors,
            "authors_with_publications": authors_with_publications,
            "total_publications": total_publications,
            "average_publications_per_author": total_publications / total_authors if total_authors > 0 else 0,
            "authors_with_affiliation": authors_with_affiliation,
            "authors_with_email": authors_with_email,
            "institutional_authors": institutional_authors,
            "flagged_authors": flagged_authors
        }
    
    def _format_timestamp(self, timestamp: Optional[float]) -> Optional[str]:
        """Convert Unix timestamp to readable date string."""
        if timestamp is None:
            return None
        try:
            return datetime.fromtimestamp(timestamp).isoformat()
        except (ValueError, OSError):
            return str(timestamp)
    
    def extract_authors(self) -> Dict[str, Any]:
        """Main method to extract authors and their publications."""
        print(f"Connecting to database: {self.database_path}")
        
        with self.connect_database() as conn:
            print("Extracting authors...")
            authors = self.get_authors(conn)
            
            print("Extracting author publications...")
            author_publications = self.get_author_publications(conn)
            
            print("Building authors with publications...")
            authors_list = self.build_authors_with_publications(authors, author_publications)
            
            print("Generating statistics...")
            statistics = self.get_author_statistics(authors)
            
            result = {
                "metadata": {
                    "database_path": self.database_path,
                    "extraction_date": datetime.now().isoformat(),
                    "statistics": statistics
                },
                "authors": authors_list
            }
            
            return result
    
    def save_json(self, data: Dict[str, Any], output_path: str = "papers3_authors.json"):
        """Save the authors data to a JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Authors data saved to: {output_path}")


def main():
    """Main function to run the authors extractor."""
    # Parse command line arguments
    args = sys.argv[1:]
    database_path = "Database.papersdb"
    full_export = False
    human_readable = False
    include_all = False
    
    for arg in args:
        if arg == "--full":
            full_export = True
        elif arg == "--human-readable":
            human_readable = True
        elif arg == "--include-all":
            include_all = True
        elif not arg.startswith("--"):
            database_path = arg
    
    try:
        # Create extractor and extract data
        extractor = Papers3AuthorsExtractor(database_path, full_export, human_readable, include_all)
        authors_data = extractor.extract_authors()
        
        # Save to JSON file
        output_file = "papers3_authors.json"
        if full_export:
            output_file = "papers3_authors_full.json"
        elif human_readable:
            output_file = "papers3_authors_human.json"
        if include_all:
            output_file = output_file.replace(".json", "_all.json")
        extractor.save_json(authors_data, output_file)
        
        # Print summary
        stats = authors_data["metadata"]["statistics"]
        if full_export:
            export_type = "Full"
        elif human_readable:
            export_type = "Human-Readable"
        else:
            export_type = "Lightweight"
        scope = "All Authors" if include_all else "Authors with Publications Only"
        print(f"\nExtraction Summary ({export_type} Export, {scope}):")
        print(f"  Total authors: {stats['total_authors']}")
        print(f"  Authors with publications: {stats['authors_with_publications']}")
        print(f"  Total publications: {stats['total_publications']}")
        print(f"  Average publications per author: {stats['average_publications_per_author']:.1f}")
        print(f"  Authors with affiliation: {stats['authors_with_affiliation']}")
        print(f"  Authors with email: {stats['authors_with_email']}")
        print(f"  Institutional authors: {stats['institutional_authors']}")
        print(f"  Flagged authors: {stats['flagged_authors']}")
        print(f"  Output file: {output_file}")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 