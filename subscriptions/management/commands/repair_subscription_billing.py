"""Audit legacy remote plans; explicitly apply cancellation without charging."""
from django.core.management.base import BaseCommand, CommandError

from payments.paystack import paystack_api
from subscriptions.billing import paystack_interval, queue_cancellation
from subscriptions.models import Subscription, SubscriptionCancellation
from subscriptions.tasks import enforce_overdue_subscriptions, process_subscription_cancellations
from tiers.models import BusinessTier, VendorTierSubscription


class Command(BaseCommand):
    help = 'Dry-run legacy billing repair. --apply disables legacy mandates and expires overdue access; never charges.'

    def add_arguments(self, parser):
        parser.add_argument('--plan-id', type=int, help='Limit remote repair to a Paystack plan ID.')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        from subscriptions.models import Plan
        apply = options['apply']
        found = False
        for model in (Plan, BusinessTier):
            plans = model.objects.exclude(paystack_plan_code__isnull=True).exclude(paystack_plan_code='')
            if options['plan_id']:
                plans = plans.filter(paystack_plan_id=options['plan_id'])
            for plan in plans:
                found = True
                expected = paystack_interval(plan)
                remote = paystack_api.fetch_plan(plan.paystack_plan_code)
                if not remote.get('status'):
                    raise CommandError(f'Unable to inspect plan {plan.pk}; nothing inferred from the failure.')
                data = remote['data']
                remote_id = data['id']
                self.stdout.write(f'Plan {remote_id} {plan.name}: {data.get("interval")} -> {expected}; manual renewal')
                page = 1
                affected = []
                while True:
                    result = paystack_api.list_subscriptions(plan=remote_id, perPage=100, page=page)
                    if not result.get('status'):
                        raise CommandError(f'Unable to list subscriptions for plan {remote_id}, page {page}')
                    rows = result.get('data') or []
                    for row in rows:
                        code = row.get('subscription_code')
                        if not code or row.get('status') in ('cancelled', 'complete', 'non-renewing'):
                            continue
                        affected.append(code)
                        self.stdout.write(f'  {code}: stop recurring billing; preserve any unexpired local paid access')
                        if apply:
                            queue_cancellation(code, row.get('email_token') or '', 'Legacy billing repair: manual renewal')
                    pages = (result.get('meta') or {}).get('pageCount')
                    if (pages is not None and page >= int(pages)) or not rows or (pages is None and len(rows) < 100):
                        break
                    page += 1
                if apply:
                    # Cancellation is the immediate safety step. Changing the
                    # plan alone does not remove existing remote mandates.
                    process_subscription_cancellations()
                    pending = SubscriptionCancellation.objects.filter(
                        subscription_code__in=affected, completed_at__isnull=True).count()
                    if pending:
                        raise CommandError(f'{pending} cancellation(s) remain pending. Restart workers and inspect the cancellation queue.')
                    if data.get('interval') != expected:
                        updated = paystack_api.update_plan(plan.paystack_plan_code,
                            interval=expected, update_existing_subscriptions=False)
                        if not updated.get('status'):
                            raise CommandError('Mandates stopped, but Paystack plan interval update failed.')
                        checked = paystack_api.fetch_plan(plan.paystack_plan_code)
                        if not checked.get('status') or checked['data'].get('interval') != expected:
                            raise CommandError('Paystack did not confirm the corrected plan interval.')
        if options['plan_id'] and not found:
            raise CommandError('No local offering matches that Paystack plan ID. Run against the correct deployment database.')
        for model in (Subscription, VendorTierSubscription):
            count = sum(sub.is_overdue for sub in model.objects.all().iterator())
            self.stdout.write(f'{model._meta.label}: {count} records require expiry/reconciliation')
        if apply:
            self.stdout.write(str(enforce_overdue_subscriptions()))
            self.stdout.write(str(process_subscription_cancellations()))
        else:
            self.stdout.write('DRY RUN: no local or remote changes. Review, then rerun with --apply.')
