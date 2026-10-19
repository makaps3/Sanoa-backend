"""
Management command to train / retrain the XGBoost negotiation models.

Usage:
    python manage.py train_negotiation_models           # synthetic bootstrap
    python manage.py train_negotiation_models --retrain # retrain from real data
    python manage.py train_negotiation_models --clear   # wipe cached models first
"""
from django.core.management.base import BaseCommand

from negotiations.ml_models import clear_model_cache, retrain_from_history, train_all_models


class Command(BaseCommand):
    help = 'Train or retrain XGBoost models for the AI negotiation chatbot'

    def add_arguments(self, parser):
        parser.add_argument(
            '--retrain', action='store_true',
            help='Retrain from real NegotiationOffer data (needs >=50 resolved offers)',
        )
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete cached models before training',
        )

    def handle(self, *args, **options):
        if options['clear']:
            clear_model_cache()
            self.stdout.write('Cached models cleared.')

        if options['retrain']:
            self.stdout.write('Retraining from real NegotiationOffer data …')
            result = retrain_from_history()
            if result:
                self.stdout.write(self.style.SUCCESS(
                    f'Models retrained from {result} real offers.'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    'Not enough resolved offers (need >=50). Run without --retrain to bootstrap.'
                ))
        else:
            self.stdout.write('Training XGBoost models on synthetic data …')
            scores = train_all_models()
            self.stdout.write(self.style.SUCCESS('Done!'))
            for name, score in scores.items():
                self.stdout.write(f'  {name}: {score:.4f}')
