"""KB Structurer parsers."""
from .csv_parser import csv_to_menu
from .xlsx_parser import xlsx_to_faq
from .docx_parser import docx_to_process
from .manual import from_template

__all__ = ["csv_to_menu", "xlsx_to_faq", "docx_to_process", "from_template"]