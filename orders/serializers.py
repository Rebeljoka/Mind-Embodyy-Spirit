from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from .models import Order, OrderItem, Address
from django.contrib.auth import get_user_model
User = get_user_model()


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("product_title", "product_sku", "unit_price", "quantity")


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "address_type", "full_name", "line1", "line2",
            "city", "region", "postal_code", "country", "phone"
        )


class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    shipping_address = AddressSerializer(write_only=True, required=False)

    class Meta:
        model = Order
        fields = ("order_number", "guest_email", "status",
                  "total", "items", "shipping_address")
        read_only_fields = ("order_number", "total")

    def validate_items(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError(
                "Order must contain at least one item")
        for i, it in enumerate(value):
            if it.get("quantity", 0) <= 0:
                raise serializers.ValidationError({i: "Quantity must be > 0"})
            if Decimal(str(it.get("unit_price", "0"))) <= 0:
                raise serializers.ValidationError(
                    {i: "Unit price must be > 0"})
        return value

    def validate(self, attrs):
        # Require guest_email for anonymous requests; authenticated users OK
        request = self.context.get("request")

        # Allow callers/tests to supply a user directly in context
        user = self.context.get("user") or None

        # Try DRF request.user first, then underlying HttpRequest.user
        if not user and request is not None:
            user = getattr(request, "user", None)
        if (not user and request is not None and
                getattr(request, "_request", None) is not None):
            user = getattr(request._request, "user", None)
        # If the view provided an explicit is_authenticated flag in context,
        # trust it (conservative)
        if self.context.get("is_authenticated") is not None:
            is_auth = bool(self.context.get("is_authenticated"))
        else:
            # Consider authenticated if user is present and has a PK or
            # .is_authenticated is True
            is_auth = (bool(user and getattr(user, "pk", None) is not None) or
                       bool(getattr(user, "is_authenticated", False)))

        if not is_auth and not attrs.get("guest_email"):
            raise serializers.ValidationError(
                {"guest_email": "Guest checkout requires guest_email"})

        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        shipping = validated_data.pop("shipping_address", None)

        # Calculate total from items (avoid trusting client total)
        total = Decimal("0.00")
        for it in items_data:
            unit = Decimal(str(it.get("unit_price", "0")))
            qty = int(it.get("quantity", 1))
            total += (unit * qty)

        validated_data["total"] = total.quantize(Decimal("0.01"))

        # Create order and related objects transactionally
        with transaction.atomic():
            # attach authenticated user if present on the request
            user = None
            if self.context.get("request") is not None:
                user = getattr(self.context.get("request"), "user", None)
            if user and getattr(user, "is_authenticated", False):
                validated_data["user"] = user

            # Reserve single-item StockItems if applicable and snapshot
            # product status
            from gallery.models import StockItem

            # collect SKUs from request
            skus = [it.get("product_sku")
                    for it in items_data if it.get("product_sku")]
            sku_map = {}
            if skus:
                products = list(
                    StockItem.objects.select_for_update().filter(sku__in=skus))
                sku_map = {p.sku: p for p in products}

            order = Order.objects.create(**validated_data)
            if shipping:
                Address.objects.create(
                    order=order, address_type=Address.SHIPPING, **shipping)

            for it in items_data:
                sku = it.get("product_sku")
                prod_status = None
                if sku:
                    p = sku_map.get(sku)
                    if p:
                        qty = int(it.get("quantity", 1))
                        # If single-item painting treat reservation as status
                        # flip only when qty == 1
                        if getattr(p, 'is_unique', False):
                            if qty == 1 and p.status == 'available':
                                p.status = 'reserved'
                                p.save()
                        # snapshot after any potential change
                        prod_status = p.status
                OrderItem.objects.create(
                    order=order, product_status=prod_status, **it)

        return order
