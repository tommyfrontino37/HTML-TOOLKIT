HTML-TOOLKIT
Convert a text PDF into a readable, self-contained, paged HTML book with optional annotations.
Windows quick start
Open Git Bash in this folder and install the Python dependencies:
```bash
python -m pip install pymupdf pillow
```
Convert a PDF:
```bash
python annotator-toolkit/pdf\_to\_book.py \\
  --pdf "C:/path/to/book.pdf" \\
  --out "book.html" \\
  --title "Book title" \\
  --author "Author name"
```
Build the enhanced annotated edition:
```bash
python annotator-toolkit/build\_enhanced.py \\
  --input "book.html" \\
  --output "book-annotated.html" \\
  --title "Book title" \\
  --author "Author name" \\
  --prefix "book-slug" \\
  --slug "book-slug" \\
  --picker "book-file" \\
 
```
Each book receives unique browser storage keys based on `--prefix`, so highlights,
notes, themes, and saved file handles cannot leak between books.
Offline dictionary
By default, the enhanced build creates a dictionary containing only words found
in the book. It uses the included theological glossary first, then WordNet and
Webster's 1913 where available. The dictionary is embedded as JSON inside the
HTML file; no internet connection is needed when reading the finished book.

