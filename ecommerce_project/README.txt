ShopKart – Real Product Photo Downloader Package

IMPORTANT:
This package contains a ready-to-run downloader rather than copied marketplace/stock
photos. The execution environment used to create this ZIP cannot directly download
101 external web images. The included script searches Wikimedia Commons and downloads
one real photograph per ShopKart product into media/products/<category>/.

Why this approach:
- Uses real photographs rather than generated icons.
- Avoids scraping Amazon/Flipkart or other competing stores.
- Wikimedia Commons provides source/license metadata.
- You can review/replace any image before using it in your project.

HOW TO USE
1. Extract this ZIP.
2. Open a terminal in the extracted folder.
3. Run:
       pip install -r requirements.txt
       python download_product_photos.py
4. The photos will be created under:
       media/products/<category>/
5. Copy that media/products folder into your Django project.
6. Review the downloaded images and their attribution/source data before publishing.

The script creates:
- JPG/PNG/WebP image files where available
- image_manifest.csv with source page, author/license information when available
- failed_downloads.txt for products that need another source

The product list is based on the products visible in your ShopKart screenshots.
