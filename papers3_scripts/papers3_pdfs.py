#!/usr/bin/env python3
"""
Papers3 PDFs Extractor

This script extracts all PDFs from a Papers3 database
and generates a JSON representation with metadata.

Usage:
    python papers3_pdfs.py [database_path] [--full] [--human-readable] [--include-all]
    
Default database path: Database.papersdb
--full: Export full publication details instead of just UUIDs
--human-readable: Use first 75 characters of title instead of UUIDs
--include-all: Include all PDFs (default: only PDFs with publications)
"""

import sqlite3
import json
import sys
import os
from typing import Dict, List, Any, Optional
from datetime import datetime


class Papers3PDFsExtractor:
    def __init__(self, database_path: str = "Database.papersdb", full_export: bool = False, human_readable: bool = False, include_all: bool = False):
        self.database_path = database_path
        self.full_export = full_export
        self.human_readable = human_readable
        self.include_all = include_all
        self.pdfs = {}
        self.pdf_publications = {}
        
    def connect_database(self) -> sqlite3.Connection:
        """Connect to the Papers3 SQLite database."""
        if not os.path.exists(self.database_path):
            raise FileNotFoundError(f"Database file not found: {self.database_path}")
        
        return sqlite3.connect(self.database_path)
    
    def get_pdfs(self, conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
        """Extract all PDFs with their metadata."""
        cursor = conn.cursor()
        
        query = """
        SELECT 
            uuid,
            caption,
            fingerprint,
            md5,
            mime_type,
            pages,
            is_primary,
            is_alias,
            missing,
            needs_ocr,
            rotation,
            type,
            searchresult,
            created_at,
            updated_at,
            object_id,
            path,
            original_path
        FROM PDF
        ORDER BY caption
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        pdfs = {}
        for row in rows:
            pdf = {
                "uuid": row[0],
                "caption": row[1],
                "fingerprint": row[2],
                "md5": row[3],
                "mime_type": row[4],
                "pages": row[5],
                "is_primary": bool(row[6]) if row[6] is not None else None,
                "is_alias": bool(row[7]) if row[7] is not None else None,
                "missing": bool(row[8]) if row[8] is not None else None,
                "needs_ocr": bool(row[9]) if row[9] is not None else None,
                "rotation": row[10],
                "type": row[11],
                "searchresult": row[12],
                "created_at": self._format_timestamp(row[13]),
                "updated_at": self._format_timestamp(row[14]),
                "object_id": row[15],
                "path": row[16],
                "original_path": row[17],
                "publications": []
            }
            pdfs[row[0]] = pdf
            
        return pdfs
    
    def get_pdf_publications(self, conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
        """Extract all publications for each PDF."""
        cursor = conn.cursor()
        
        if self.full_export:
            # Full export with all publication details
            query = """
            SELECT 
                pdf.uuid as pdf_uuid,
                pdf.object_id,
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
            FROM PDF pdf
            JOIN Publication p ON pdf.object_id = p.uuid
            ORDER BY pdf.uuid, p.title
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            pdf_publications = {}
            for row in rows:
                item = {
                    "publication_uuid": row[1],
                    "title": row[2],
                    "author_string": row[3],
                    "publication_date": row[4],
                    "doi": row[5],
                    "publisher": row[6],
                    "volume": row[7],
                    "startpage": row[8],
                    "endpage": row[9],
                    "pages": f"{row[8]}-{row[9]}" if row[8] and row[9] else None,
                    "publication_type": row[10],
                    "rating": row[11],
                    "read_status": row[12],
                    "flagged": bool(row[13]) if row[13] is not None else False,
                    "notes": row[14],
                    "keyword_string": row[15],
                    "times_cited": row[16],
                    "times_read": row[17]
                }
                
                pdf_uuid = row[0]
                if pdf_uuid not in pdf_publications:
                    pdf_publications[pdf_uuid] = []
                pdf_publications[pdf_uuid].append(item)
        else:
            # Lightweight export with UUIDs and optionally titles
            if self.human_readable:
                query = """
                SELECT 
                    pdf.uuid as pdf_uuid,
                    pdf.object_id,
                    p.title
                FROM PDF pdf
                JOIN Publication p ON pdf.object_id = p.uuid
                ORDER BY pdf.uuid, p.title
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                pdf_publications = {}
                for row in rows:
                    title = row[2] if row[2] else "Untitled"
                    title_preview = title[:75] + "..." if len(title) > 75 else title
                    
                    item = {
                        "publication_uuid": row[1],
                        "title_preview": title_preview
                    }
                    
                    pdf_uuid = row[0]
                    if pdf_uuid not in pdf_publications:
                        pdf_publications[pdf_uuid] = []
                    pdf_publications[pdf_uuid].append(item)
            else:
                query = """
                SELECT 
                    pdf.uuid as pdf_uuid,
                    pdf.object_id
                FROM PDF pdf
                WHERE pdf.object_id IS NOT NULL
                ORDER BY pdf.uuid
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                pdf_publications = {}
                for row in rows:
                    item = {
                        "publication_uuid": row[1]
                    }
                    
                    pdf_uuid = row[0]
                    if pdf_uuid not in pdf_publications:
                        pdf_publications[pdf_uuid] = []
                    pdf_publications[pdf_uuid].append(item)
            
        return pdf_publications
    
    def build_pdfs_with_publications(self, pdfs: Dict[str, Dict[str, Any]], 
                                   pdf_publications: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Build the PDFs list with their publications."""
        # Add publications to PDFs
        for pdf_uuid, publications in pdf_publications.items():
            if pdf_uuid in pdfs:
                if self.full_export:
                    pdfs[pdf_uuid]["publications"] = publications
                else:
                    if self.human_readable:
                        # For human-readable export, store title previews
                        pdfs[pdf_uuid]["publications"] = [pub["title_preview"] for pub in publications]
                    else:
                        # For lightweight export, just store the UUIDs
                        pdfs[pdf_uuid]["publications"] = [pub["publication_uuid"] for pub in publications]
                pdfs[pdf_uuid]["publication_count"] = len(publications)
        
        # Filter PDFs based on include_all parameter
        if not self.include_all:
            # Only include PDFs with publications
            pdfs_list = [pdf for pdf in pdfs.values() if pdf.get("publications")]
        else:
            # Include all PDFs
            pdfs_list = list(pdfs.values())
        
        # Sort by caption
        pdfs_list.sort(key=lambda x: (x.get("caption") or "", x.get("uuid") or ""))
        
        return pdfs_list
    
    def get_pdf_statistics(self, pdfs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Generate statistics about the PDFs."""
        total_pdfs = len(pdfs)
        
        if self.full_export:
            total_publications = sum(len(p.get("publications", [])) for p in pdfs.values())
            pdfs_with_publications = sum(1 for p in pdfs.values() if p.get("publications"))
        else:
            total_publications = sum(len(p.get("publications", [])) for p in pdfs.values())
            pdfs_with_publications = sum(1 for p in pdfs.values() if p.get("publications"))
        
        primary_pdfs = sum(1 for p in pdfs.values() if p.get("is_primary"))
        alias_pdfs = sum(1 for p in pdfs.values() if p.get("is_alias"))
        missing_pdfs = sum(1 for p in pdfs.values() if p.get("missing"))
        needs_ocr_pdfs = sum(1 for p in pdfs.values() if p.get("needs_ocr"))
        
        total_pages = sum(p.get("pages", 0) or 0 for p in pdfs.values())
        
        return {
            "total_pdfs": total_pdfs,
            "pdfs_with_publications": pdfs_with_publications,
            "total_publications": total_publications,
            "average_publications_per_pdf": total_publications / total_pdfs if total_pdfs > 0 else 0,
            "primary_pdfs": primary_pdfs,
            "alias_pdfs": alias_pdfs,
            "missing_pdfs": missing_pdfs,
            "needs_ocr_pdfs": needs_ocr_pdfs,
            "total_pages": total_pages,
            "average_pages_per_pdf": total_pages / total_pdfs if total_pdfs > 0 else 0
        }
    
    def _format_timestamp(self, timestamp: Optional[float]) -> Optional[str]:
        """Convert Unix timestamp to readable date string."""
        if timestamp is None:
            return None
        try:
            return datetime.fromtimestamp(timestamp).isoformat()
        except (ValueError, OSError):
            return str(timestamp)
    
    def extract_pdfs(self) -> Dict[str, Any]:
        """Main method to extract PDFs and their publications."""
        print(f"Connecting to database: {self.database_path}")
        
        with self.connect_database() as conn:
            print("Extracting PDFs...")
            pdfs = self.get_pdfs(conn)
            
            print("Extracting PDF publications...")
            pdf_publications = self.get_pdf_publications(conn)
            
            print("Building PDFs with publications...")
            pdfs_list = self.build_pdfs_with_publications(pdfs, pdf_publications)
            
            print("Generating statistics...")
            statistics = self.get_pdf_statistics(pdfs)
            
            result = {
                "metadata": {
                    "database_path": self.database_path,
                    "extraction_date": datetime.now().isoformat(),
                    "statistics": statistics
                },
                "pdfs": pdfs_list
            }
            
            return result
    
    def save_json(self, data: Dict[str, Any], output_path: str = "papers3_pdfs.json"):
        """Save the PDFs data to a JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"PDFs data saved to: {output_path}")


def main():
    """Main function to run the PDFs extractor."""
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
        extractor = Papers3PDFsExtractor(database_path, full_export, human_readable, include_all)
        pdfs_data = extractor.extract_pdfs()
        
        # Save to JSON file
        output_file = "papers3_pdfs.json"
        if full_export:
            output_file = "papers3_pdfs_full.json"
        elif human_readable:
            output_file = "papers3_pdfs_human.json"
        if include_all:
            output_file = output_file.replace(".json", "_all.json")
        extractor.save_json(pdfs_data, output_file)
        
        # Print summary
        stats = pdfs_data["metadata"]["statistics"]
        if full_export:
            export_type = "Full"
        elif human_readable:
            export_type = "Human-Readable"
        else:
            export_type = "Lightweight"
        scope = "All PDFs" if include_all else "PDFs with Publications Only"
        print(f"\nExtraction Summary ({export_type} Export, {scope}):")
        print(f"  Total PDFs: {stats['total_pdfs']}")
        print(f"  PDFs with publications: {stats['pdfs_with_publications']}")
        print(f"  Total publications: {stats['total_publications']}")
        print(f"  Average publications per PDF: {stats['average_publications_per_pdf']:.1f}")
        print(f"  Primary PDFs: {stats['primary_pdfs']}")
        print(f"  Alias PDFs: {stats['alias_pdfs']}")
        print(f"  Missing PDFs: {stats['missing_pdfs']}")
        print(f"  PDFs needing OCR: {stats['needs_ocr_pdfs']}")
        print(f"  Total pages: {stats['total_pages']}")
        print(f"  Average pages per PDF: {stats['average_pages_per_pdf']:.1f}")
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