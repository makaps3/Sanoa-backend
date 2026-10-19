"""
XGBoost-powered AI negotiation engine.

The AI acts as the vendor's representative.  When a buyer submits an offer,
respond_to_offer() evaluates it and returns one of:
  accept  — price agreed, room can close
  counter — AI proposes a higher counter-offer
  reject  — offer is below the hard floor

One singleton (_engine) is kept in module scope so the models are loaded from
disk only once per worker process.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from .ml_models import (
    extract_offer_features,
    get_acceptance_model,
    get_counter_model,
    train_all_models,
)

logger = logging.getLogger('sanoa.negotiations')

_ACTION_ACCEPT = 2
_ACTION_COUNTER = 1
_ACTION_REJECT = 0

_engine = None  # module-level singleton


def get_engine():
    global _engine
    if _engine is None:
        _engine = NegotiationAIEngine()
    return _engine


class NegotiationAIEngine:
    """
    Loads XGBoost models once, then answers individual offer requests.
    Thread-safe for concurrent WebSocket consumers (prediction is read-only).
    """

    def __init__(self):
        self._clf = get_acceptance_model()
        self._reg = get_counter_model()

        if self._clf is None or self._reg is None:
            logger.info("No trained models found — bootstrapping on synthetic data …")
            train_all_models()
            self._clf = get_acceptance_model()
            self._reg = get_counter_model() #

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_opening_message(self, room) -> str:
        """Greeting sent when a buyer connects to an AI-mode room."""
        product = room.product
        policy = self._policy(room.vendor)
        vendor_name = (
            getattr(room.vendor, 'trading_name', None)
            or getattr(room.vendor, 'name', None)
            or 'our store'
        )
        return (
            f"Hi! I'm the AI negotiator for {vendor_name}. "
            f"The listed price for **{product.name}** is R{product.price:.2f}. "
            f"I can offer up to {policy['max_discount']:.0f}% off depending on your offer. "
            f"What price would you like to propose?"
        )

    def respond_to_offer(self, room, offered_price) -> dict:
        """
        Evaluate a buyer's price offer and return an AI response dict:

          {
            'action'       : 'accept' | 'counter' | 'reject',
            'counter_price': Decimal | None,
            'final_price'  : Decimal | None,
            'message'      : str,
            'confidence'   : float,
          }
        """
        product = room.product
        original = Decimal(str(product.price))
        offered = Decimal(str(offered_price))

        policy = self._policy(room.vendor)
        max_discount = Decimal(str(policy['max_discount']))
        floor_price = (original * (1 - max_discount / 100)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        # Feature vector
        offer_ratio = float(offered / original) if original > 0 else 1.0
        demand_score = self._demand_score(product)
        vendor_margin = float(max_discount) / 100
        round_n = self._round_number(room)
        hours_elapsed = (timezone.now() - room.created_at).total_seconds() / 3600
        time_ratio = min(1.0, hours_elapsed / 24)

        features = extract_offer_features(
            offer_ratio, demand_score, vendor_margin, round_n, time_ratio
        )

        # Predict
        proba = self._clf.predict_proba(features.reshape(1, -1))[0]
        action = int(proba.argmax())
        confidence = float(proba.max())

        # Hard overrides
        if offered >= original:
            action, confidence = _ACTION_ACCEPT, 0.99
        elif offered < floor_price * Decimal('0.85'):
            action, confidence = _ACTION_REJECT, 0.97

        if action == _ACTION_ACCEPT:
            return {
                'action': 'accept',
                'counter_price': None,
                'final_price': offered,
                'message': (
                    f"Great news — I accept your offer of R{offered:.2f}! "
                    f"Please checkout within 24 hours to lock in this price."
                ),
                'confidence': confidence,
            }

        if action == _ACTION_COUNTER:
            counter_ratio = float(self._reg.predict(features.reshape(1, -1))[0])
            floor_ratio = float(floor_price / original)
            counter_ratio = max(floor_ratio, min(1.0, counter_ratio))
            counter_price = (original * Decimal(str(counter_ratio))).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            counter_price = max(floor_price, counter_price)

            # Never counter below buyer's offer
            if counter_price <= offered:
                counter_price = max(offered + Decimal('1.00'), floor_price)

            diff = counter_price - offered
            return {
                'action': 'counter',
                'counter_price': counter_price,
                'final_price': None,
                'message': (
                    f"Thanks for your offer! How about R{counter_price:.2f}? "
                    f"That's only R{diff:.2f} more than what you proposed."
                ),
                'confidence': confidence,
            }

        # reject
        return {
            'action': 'reject',
            'counter_price': None,
            'final_price': None,
            'message': (
                f"I'm sorry, I can't go that low. "
                f"The lowest I can offer is R{floor_price:.2f}. "
                f"Feel free to make a revised offer."
            ),
            'confidence': confidence,
            'floor_price': floor_price,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _policy(self, vendor) -> dict:
        try:
            p = vendor.price_policy
            return {
                'max_discount': float(p.max_discount_percent),
                'max_markup':   float(p.max_markup_percent),
                'min_floor':    float(p.min_floor_percent),
            }
        except Exception:
            return {'max_discount': 10.0, 'max_markup': 15.0, 'min_floor': 5.0}

    def _demand_score(self, product) -> float:
        sales = getattr(product, 'sales_count', 0) or 0
        views = getattr(product, 'views_count', 0) or 0
        return min(1.0, (sales * 2 + views * 0.01) / 100)

    def _round_number(self, room) -> int:
        return room.offers.count() + 1
