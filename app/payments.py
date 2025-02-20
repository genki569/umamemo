import stripe
from flask import current_app
from app.models import ReviewPurchase
from app import db

class PaymentManager:
    @staticmethod
    def create_payment_intent(review, user):
        """Stripe PaymentIntentの作成"""
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        
        try:
            # PaymentIntentを作成
            intent = stripe.PaymentIntent.create(
                amount=review.price,
                currency='jpy',
                metadata={
                    'review_id': review.id,
                    'user_id': user.id
                }
            )
            
            # 仮の購入レコードを作成
            purchase = ReviewPurchase(
                user_id=user.id,
                review_id=review.id,
                price_paid=review.price,
                status='pending',
                payment_intent_id=intent.id
            )
            db.session.add(purchase)
            db.session.commit()
            
            return {
                'client_secret': intent.client_secret,
                'purchase_id': purchase.id
            }
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error: {str(e)}")
            raise

    @staticmethod
    def confirm_payment(payment_intent_id):
        """支払い完了後の処理"""
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            purchase = ReviewPurchase.query.filter_by(
                payment_intent_id=payment_intent_id
            ).first()
            
            if intent.status == 'succeeded' and purchase:
                purchase.status = 'completed'
                db.session.commit()
                return True
                
            return False
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error: {str(e)}")
            return False 