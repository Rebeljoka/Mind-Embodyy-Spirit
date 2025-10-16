// Checkout JavaScript for Stripe payment integration
document.addEventListener('DOMContentLoaded', function() {
    console.log('Checkout JavaScript loaded');

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
    console.log('Payment mode:', isPaymentMode);

    if (isPaymentMode) {
        console.log('Entering payment completion mode');
        // Payment completion mode
        const paymentElement = document.getElementById('payment-element');
        const completePaymentBtn = document.getElementById('complete-payment-btn');

        if (paymentElement && completePaymentBtn) {
            // Get client secret from URL parameters
            const urlParams = new URLSearchParams(window.location.search);
            const clientSecret = urlParams.get('payment_intent_client_secret');
            console.log('Client secret from URL:', clientSecret ? 'present' : 'missing');

            if (clientSecret) {
                console.log('Creating Stripe Elements for payment completion');
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
        console.log('Entering checkout mode');
        // Checkout mode - handle form submission and payment setup
        const checkoutForm = document.getElementById('checkout-form');
        const submitBtn = document.getElementById('submit-btn');
        const paymentElement = document.getElementById('payment-element');

        console.log('Form elements found:', {
            checkoutForm: !!checkoutForm,
            submitBtn: !!submitBtn,
            paymentElement: !!paymentElement
        });

        if (checkoutForm && submitBtn && paymentElement) {
            console.log('Adding form submit listener');
            checkoutForm.addEventListener('submit', async function(e) {
                console.log('Form submitted');
                e.preventDefault(); // Prevent default form submission

                submitBtn.disabled = true;
                submitBtn.textContent = 'Processing...';

                try {
                    // Collect form data
                    const formData = new FormData(checkoutForm);
                    const orderData = {
                        items: [], // Will be populated from cart
                        shipping_address: {
                            full_name: formData.get('shipping_full_name'),
                            line1: formData.get('shipping_line1'),
                            line2: formData.get('shipping_line2') || '',
                            city: formData.get('shipping_city'),
                            region: formData.get('shipping_region') || '',
                            postal_code: formData.get('shipping_postal_code'),
                            country: formData.get('shipping_country'),
                            phone: formData.get('shipping_phone') || '',
                        }
                    };

                    // Add guest email if not authenticated
                    const guestEmail = formData.get('guest_email');
                    if (guestEmail) {
                        orderData.guest_email = guestEmail;
                    }

                    // Add billing address if different and fields are filled
                    const sameAddress = formData.get('same-address') === 'on';
                    if (!sameAddress) {
                        const billingFullName = formData.get('billing_full_name')?.trim();
                        const billingLine1 = formData.get('billing_line1')?.trim();
                        const billingCity = formData.get('billing_city')?.trim();
                        const billingPostalCode = formData.get('billing_postal_code')?.trim();
                        const billingCountry = formData.get('billing_country')?.trim();

                        // Only send billing address if required fields are filled
                        if (billingFullName && billingLine1 && billingCity && billingPostalCode && billingCountry) {
                            orderData.billing_address = {
                                full_name: billingFullName,
                                line1: billingLine1,
                                line2: formData.get('billing_line2')?.trim() || '',
                                city: billingCity,
                                region: formData.get('billing_region')?.trim() || '',
                                postal_code: billingPostalCode,
                                country: billingCountry,
                                phone: formData.get('billing_phone')?.trim() || '',
                            };
                        }
                    }

                    // Get cart items from the page (they're rendered in the template)
                    const cartItems = document.querySelectorAll('[data-cart-item]');
                    cartItems.forEach(item => {
                        const title = item.querySelector('[data-product-title]')?.textContent?.trim();
                        const skuElement = item.querySelector('[data-product-sku]');
                        const sku = skuElement ? skuElement.textContent?.replace('SKU: ', '').trim() : '';
                        const quantity = parseInt(item.querySelector('[data-quantity]')?.textContent?.replace('Qty: ', '').trim() || '1');
                        const unitPrice = parseFloat(item.querySelector('[data-unit-price]')?.getAttribute('data-unit-price') || '0');

                        if (title && unitPrice > 0) {
                            orderData.items.push({
                                product_title: title,
                                product_sku: sku,
                                unit_price: unitPrice,
                                quantity: quantity
                            });
                        }
                    });

                    console.log('Order data being sent:', orderData);

                    // Create order via API
                    const orderResponse = await fetch('/orders/create/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value
                        },
                        body: JSON.stringify(orderData)
                    });

                    if (!orderResponse.ok) {
                        const errorData = await orderResponse.json();
                        console.error('Order creation failed:', errorData);
                        throw new Error(`Failed to create order: ${JSON.stringify(errorData)}`);
                    }

                    const orderResult = await orderResponse.json();
                    const orderId = orderResult.id;

                    // Start payment for the order
                    const paymentResponse = await fetch(`/orders/start-payment/${orderId}/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value
                        }
                    });

                    if (!paymentResponse.ok) {
                        throw new Error('Failed to start payment');
                    }

                    const paymentResult = await paymentResponse.json();
                    const clientSecret = paymentResult.client_secret;

                    // Create and mount Stripe Elements with clientSecret
                    elements = stripe.elements({ clientSecret });
                    cardElement = elements.create('payment');
                    cardElement.mount('#payment-element');

                    // Hide the placeholder message and show the payment form
                    const placeholder = paymentElement.querySelector('.alert');
                    if (placeholder) {
                        placeholder.style.display = 'none';
                    }

                    // Update submit button to handle payment
                    submitBtn.textContent = 'Complete Payment';
                    submitBtn.disabled = false;

                    // Add payment completion handler
                    submitBtn.addEventListener('click', async function() {
                        submitBtn.disabled = true;
                        submitBtn.textContent = 'Processing Payment...';

                        try {
                            // Submit elements first as required by Stripe
                            const { error: submitError } = await elements.submit();
                            if (submitError) {
                                console.error('Payment submission failed:', submitError);
                                alert('Payment failed: ' + submitError.message);
                                submitBtn.disabled = false;
                                submitBtn.textContent = 'Complete Payment';
                                return;
                            }

                            const { error, paymentIntent } = await stripe.confirmPayment({
                                elements,
                                clientSecret,
                                confirmParams: {
                                    return_url: window.location.origin + `/orders/order/${orderId}/success/`,
                                },
                            });

                            if (error) {
                                console.error('Payment failed:', error);
                                alert('Payment failed: ' + error.message);
                                submitBtn.disabled = false;
                                submitBtn.textContent = 'Complete Payment';
                            } else if (paymentIntent.status === 'succeeded') {
                                // Redirect to success page
                                window.location.href = `/orders/order/${orderId}/success/`;
                            }
                        } catch (err) {
                            console.error('Payment error:', err);
                            alert('An error occurred during payment. Please try again.');
                            submitBtn.disabled = false;
                            submitBtn.textContent = 'Complete Payment';
                        }
                    });

                } catch (error) {
                    console.error('Checkout error:', error);
                    alert('An error occurred: ' + error.message);
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Complete Order';
                }
            });
        }

        // Handle billing address logic
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