# Mind-Embodyy-Spirit

A Django-based e-commerce platform with integrated order management, payment processing, and inventory handling.

## Features

### Orders App

The orders app provides comprehensive order management functionality with the following features:

#### Core Models
- **Order**: Main order entity with status tracking (paid, processing, shipped, cancelled, refunded)
- **OrderItem**: Individual items within orders with snapshot data for audit trails
- **Address**: Shipping and billing addresses associated with orders
- **PaymentRecord**: Payment tracking with provider integration and idempotency
- **Reservation**: Item reservations during checkout to prevent overselling
- **ProcessedEvent**: Webhook event deduplication for idempotent processing

#### API Endpoints
- `POST /orders/create/` - Create orders (authenticated or guest)
- `POST /orders/start-payment/<order_id>/` - Initiate payment processing
- `POST /orders/webhook/` - Handle Stripe webhook events
- `POST /orders/refund/<payment_id>/` - Issue refunds (staff only)
- `GET /orders/schema/` - API schema documentation

#### Payment Integration
- **Stripe Integration**: Full payment intent creation and webhook handling
- **Idempotent Operations**: Prevents duplicate payments and refunds
- **Multi-currency Support**: Configurable currency per order
- **Payment Status Tracking**: Pending, succeeded, failed, refunded states

#### Stock Management
- **Atomic Stock Decrements**: Prevents overselling with database transactions
- **Reservation System**: Locks items during checkout (4-hour default expiry)
- **Stock Shortage Detection**: Flags orders when inventory is insufficient
- **Unique Item Handling**: Special logic for one-of-a-kind items

#### Admin Interface
- **Order Management**: View, filter, and search orders
- **Bulk Actions**: Mark orders as shipped or refunded
- **Payment Management**: View payment records and issue refunds
- **Reservation Oversight**: Monitor active reservations
- **Address Management**: Handle shipping/billing addresses

#### Webhook Processing
- **Event Deduplication**: Prevents processing duplicate webhook events
- **Payment Success Handling**: Updates order status and decrements stock
- **Email Notifications**: Automatic order confirmation emails
- **Error Resilience**: Continues processing even if email sending fails

#### Security & Middleware
- **JSON-Only Enforcement**: Requires JSON content-type for order creation
- **Staff-Only Refunds**: Administrative controls for refund operations
- **CSRF Protection**: Standard Django security measures
- **Input Validation**: Comprehensive serializer validation

#### Email Integration
- **Order Confirmations**: Automatic emails on successful payment
- **Configurable Senders**: Uses Django's DEFAULT_FROM_EMAIL setting
- **Error Handling**: Email failures don't block order processing

## Technology Stack

- **Backend**: Django 5.2 with Django REST Framework
- **Database**: PostgreSQL (configurable via DATABASE_URL)
- **Payments**: Stripe API integration
- **Media Storage**: Cloudinary (optional, falls back to local storage)
- **Authentication**: Django Allauth with social login support
- **Frontend**: Django templates with Tailwind CSS
- **Testing**: Comprehensive unit tests with mocking

## Configuration

### Environment Variables
- `SECRET_KEY`: Django secret key (required)
- `DEBUG`: Enable/disable debug mode
- `DATABASE_URL`: Database connection string
- `STRIPE_SECRET_KEY`: Stripe API key for payments
- `CLOUDINARY_URL`: Cloudinary storage configuration
- `ORDERS_JSON_ONLY_VIEWS`: Comma-separated list of views requiring JSON

### Settings
- `ORDERS_JSON_ONLY_VIEWS`: Views that require JSON content-type
- `DEFAULT_FROM_EMAIL`: Email sender address for notifications

## Installation & Setup

1. Clone the repository
2. Create virtual environment: `python -m venv .venv`
3. Activate environment: `.venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Set environment variables
6. Run migrations: `python manage.py migrate`
7. Create superuser: `python manage.py createsuperuser`
8. Run tests: `python manage.py test`
9. Start server: `python manage.py runserver`

## Testing

Run the full test suite:
```bash
python manage.py test
```

Run orders app tests specifically:
```bash
python manage.py test orders
```

## API Usage Examples

### Create Order (Guest)
```json
POST /orders/create/
Content-Type: application/json

{
  "guest_email": "customer@example.com",
  "items": [
    {
      "product_title": "Art Print",
      "product_sku": "ART-001",
      "unit_price": "25.00",
      "quantity": 1
    }
  ]
}
```

### Start Payment
```json
POST /orders/start-payment/123/
```

Response includes `client_secret` for Stripe Elements integration.

### Webhook Handling
Stripe webhooks are automatically processed at `/orders/webhook/` with signature verification.

## Tasks to Complete

### High Priority
1. **Complete Refund Webhook Handling**: Implement `charge.refunded` and `charge.refund.updated` event processing in `webhooks.py`
2. **Email Template System**: Replace hardcoded email bodies with Django templates
3. **Error Monitoring**: Add proper logging and error tracking for payment failures
4. **Rate Limiting**: Implement rate limiting for API endpoints

### Medium Priority
1. **Order Status Webhooks**: Send webhooks to external systems on order status changes
2. **Partial Refunds**: Support partial refund amounts in the refund API
3. **Order History**: Add order status change tracking and history
4. **Invoice Generation**: Generate PDF invoices for completed orders
5. **Multi-provider Payments**: Add support for PayPal, Klarna, etc.

### Low Priority
1. **Order Comments**: Allow customers to add notes to orders
2. **Gift Messages**: Support gift orders with custom messages
3. **Order Cancellation**: Allow customers to cancel pending orders
4. **Return Management**: Handle return requests and processing
5. **Analytics Dashboard**: Order metrics and reporting

### Technical Debt
1. **Code Coverage**: Increase test coverage for edge cases
2. **Performance Optimization**: Add database indexes for common queries
3. **API Documentation**: Complete OpenAPI schema documentation
4. **Type Hints**: Add comprehensive type annotations
5. **Error Messages**: Improve error messages for better UX

## Contributing

1. Follow PEP 8 style guidelines
2. Write comprehensive tests for new features
3. Update documentation for API changes
4. Use atomic transactions for data consistency
5. Implement idempotent operations where appropriate

## License

[Add your license information here]
