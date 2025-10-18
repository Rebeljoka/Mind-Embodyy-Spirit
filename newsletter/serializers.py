from rest_framework import serializers


class SubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    locale = serializers.CharField(required=False, allow_blank=True)
    source = serializers.CharField(required=False, allow_blank=True)


class UnsubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField()
