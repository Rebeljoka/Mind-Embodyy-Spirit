// Checkout JavaScript for Stripe payment integration
document.addEventListener('DOMContentLoaded', function() {
    // Get Stripe key from meta tag
    const stripeKey = document.querySelector('meta[name="stripe-publishable-key"]')?.content;
    if (!stripeKey) {
        console.error('Stripe publishable key not found');
        return;
    }

    const stripe = Stripe(stripeKey);
    let elements = null;
    let cardElement = null;

    // Check if we're in payment completion mode
    const isPaymentMode = document.querySelector('section[data-payment-mode="true"]') !== null;

    if (isPaymentMode) {
        // Payment completion mode
        const paymentElement = document.getElementById('payment-element');
        const completePaymentBtn = document.getElementById('complete-payment-btn');

        if (paymentElement && completePaymentBtn) {
            // Get client secret from URL parameters
            const urlParams = new URLSearchParams(window.location.search);
            const clientSecret = urlParams.get('payment_intent_client_secret');

            if (clientSecret) {
                // Create payment element
                elements = stripe.elements();
                cardElement = elements.create('payment');
                cardElement.mount('#payment-element');

                completePaymentBtn.addEventListener('click', async function() {
                    completePaymentBtn.disabled = true;
                    completePaymentBtn.textContent = 'Processing...';

                    try {
                        const { error, paymentIntent } = await stripe.confirmCardPayment(clientSecret, {
                            payment_method: {
                                card: cardElement,
                            }
                        });

                        if (error) {
                            console.error('Payment failed:', error);
                            alert('Payment failed: ' + error.message);
                            completePaymentBtn.disabled = false;
                            completePaymentBtn.textContent = 'Complete Payment';
                        } else if (paymentIntent.status === 'succeeded') {
                            // Get order_id from URL parameters
                            const orderId = urlParams.get('order_id');
                            // Redirect to success page with order_id
                            window.location.href = `/orders/order/${orderId}/success/`;
                        }
                    } catch (err) {
                        console.error('Payment error:', err);
                        alert('An error occurred during payment. Please try again.');
                        completePaymentBtn.disabled = false;
                        completePaymentBtn.textContent = 'Complete Payment';
                    }
                });
            }
        }
    } else {
        // Checkout mode - handle billing address logic
        const sameAddressCheckbox = document.getElementById('same-address');
        const billingSection = document.getElementById('billing-section');
        const billingInputs = billingSection.querySelectorAll('input, select');

        sameAddressCheckbox.addEventListener('change', function() {
            if (this.checked) {
                billingSection.classList.add('hidden');
                // Clear billing fields
                billingInputs.forEach(input => {
                    input.required = false;
                    input.value = '';
                });
            } else {
                billingSection.classList.remove('hidden');
                // Make billing fields required
                billingInputs.forEach(input => {
                    if (input.name.startsWith('billing_') && input.name !== 'billing_line2' && input.name !== 'billing_region' && input.name !== 'billing_phone') {
                        input.required = true;
                    }
                });
            }
        });

        // Copy shipping to billing when checkbox is checked
        const shippingInputs = document.querySelectorAll('input[name^="shipping_"], select[name^="shipping_"]');

        shippingInputs.forEach(input => {
            input.addEventListener('input', function() {
                if (sameAddressCheckbox.checked) {
                    const billingName = this.name.replace('shipping_', 'billing_');
                    const billingInput = document.querySelector(`[name="${billingName}"]`);
                    if (billingInput) {
                        billingInput.value = this.value;
                    }
                }
            });
        });
    }
});