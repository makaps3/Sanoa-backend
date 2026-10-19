from django.core.management.base import BaseCommand
from products.models import Product


class Command(BaseCommand):
    help = 'Generate QR codes for all products that do not have one'

    def handle(self, *args, **options):
        products = Product.objects.filter(qr_code='')
        count = products.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('All products already have QR codes.'))
            return

        self.stdout.write(f'Generating QR codes for {count} products...')

        for product in products:
            product.generate_qr_code()
            product.save(update_fields=['qr_code'])
            self.stdout.write(f'  Generated QR code for: {product.name}')

        self.stdout.write(self.style.SUCCESS(f'Successfully generated {count} QR codes.'))
