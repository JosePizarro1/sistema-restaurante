"""
Management command to download food images from free stock photo sources
and store them as base64 in Plato.imagen_base64.

Usage:
    python manage.py cargar_imagenes              # Load all seed dishes
    python manage.py cargar_imagenes --force      # Overwrite existing images too
    python manage.py cargar_imagenes --dry-run    # Preview without saving
"""

import io
import logging

import requests
from django.core.management.base import BaseCommand
from PIL import Image

from restaurante.models import Plato

logger = logging.getLogger(__name__)

# Free-to-use image sources (Unsplash, Pexels, Wikimedia Commons).
# URLs are direct links to the image file (not HTML pages).
# Format: {dish_name: image_url}
SEED_IMAGE_URLS = {
    "Sopa de Res": "https://rumbameats.com/es/lafamilia/sopa-de-res-hondurena-de-larocioisabel/",
    "Lomo Saltado": "data:image/webp;base64,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",
    "Pollo Dorado": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSI7OEXSZGNSff02p5zY9Vu_taJ-t3cTWFiRynhQJTELw&s=10",
    "Hamburguesa al Plato": "https://buenazo.pe/recetas/platos-de-fondohamburguesas-receta-paso-paso-888",
    "Chuleta de Res": "https://www.facebook.com/kritchencook/posts/chuleta-de-res-con-chorizo-al-vino-salpimentar-las-chuletas-de-res-y-asarlas-en-/271239277868650/",
}


def download_image(url: str, timeout: int = 15) -> bytes | None:
    """Download an image from a URL and return raw bytes.
    If url is already a data URI, extract and return the raw bytes.
    """
    if url.startswith("data:"):
        # Data URI: extract the base64 payload
        try:
            _header, data = url.split(",", 1)
            import base64
            return base64.b64decode(data)
        except (ValueError, base64.binascii.Error) as e:
            logger.error(f"Failed to parse data URI: {e}")
            return None

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; RestoPOS/1.0; +http://localhost)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type and "octet-stream" not in content_type:
            logger.warning(f"URL does not appear to be an image (Content-Type: {content_type})")
        return resp.content
    except requests.RequestException as e:
        logger.error(f"Failed to download {url}: {e}")
        return None


def image_to_base64(image_bytes: bytes, max_size: tuple = (400, 300), quality: int = 70) -> str:
    """Convert raw image bytes to a base64 data URI (JPEG)."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.thumbnail(max_size, Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)
    buffer.seek(0)
    encoded = __import__("base64").b64encode(buffer.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


class Command(BaseCommand):
    help = "Download food images for seed dishes and store them as base64 in Plato.imagen_base64."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing images too.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be done without saving.",
        )
        parser.add_argument(
            "--dish",
            action="append",
            default=None,
            help="Process only this dish name (can be used multiple times).",
        )

    def handle(self, *args, **options):
        force = options["force"]
        dry_run = options["dry_run"]
        dish_filter = options["dish"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be saved"))

        # Filter dishes if --dish was specified
        if dish_filter:
            dishes = {k: v for k, v in SEED_IMAGE_URLS.items() if k in dish_filter}
        else:
            dishes = SEED_IMAGE_URLS

        total = len(dishes)
        success = 0
        skipped = 0
        failed = 0

        for i, (nombre, url) in enumerate(dishes.items(), 1):
            self.stdout.write(f"[{i}/{total}] Processing: {nombre} ...")

            plato = Plato.objects.filter(nombre=nombre).first()
            if not plato:
                self.stdout.write(self.style.NOTICE(f"  ⚠ Plato '{nombre}' not found in DB, skipping."))
                failed += 1
                continue

            if plato.imagen_base64 and not force:
                self.stdout.write("  ⏭ Already has image, use --force to overwrite.")
                skipped += 1
                continue

            # Download
            image_bytes = download_image(url)
            if not image_bytes:
                self.stdout.write(self.style.ERROR("  ✗ Failed to download image."))
                failed += 1
                continue

            # Check file size (skip if > 2MB to avoid memory issues)
            if len(image_bytes) > 2 * 1024 * 1024:
                self.stdout.write(self.style.WARNING(f"  ⚠ Image too large ({len(image_bytes)} bytes), skipping."))
                failed += 1
                continue

            # Convert to base64
            try:
                base64_data = image_to_base64(image_bytes)
            except (OSError, ValueError, Image.UnidentifiedImageError) as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Failed to process image: {e}"))
                failed += 1
                continue

            # Check base64 size (should be < 500KB to be reasonable for a TextField)
            if len(base64_data) > 500 * 1024:
                self.stdout.write(self.style.WARNING(f"  ⚠ Base64 too large ({len(base64_data)} bytes), skipping."))
                failed += 1
                continue

            if dry_run:
                self.stdout.write(f"  ✓ Would set imagen_base64 ({len(base64_data)} bytes base64)")
                success += 1
                continue

            plato.imagen_base64 = base64_data
            plato.save(update_fields=["imagen_base64"])
            self.stdout.write(self.style.SUCCESS(f"  ✓ Updated imagen_base64 ({len(base64_data)} bytes base64)"))
            success += 1

        # Summary
        self.stdout.write("")
        self.stdout.write(f"Done: {success} updated, {skipped} skipped, {failed} failed out of {total}.")

        if failed > 0 and not dry_run:
            self.stdout.write(self.style.WARNING(
                "Some dishes failed. You can re-run with --dish <name> for specific dishes."
            ))
