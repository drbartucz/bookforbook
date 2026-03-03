from rest_framework import serializers

from apps.accounts.serializers import UserPublicProfileSerializer

from .models import Rating


class RatingSerializer(serializers.ModelSerializer):
    rater = UserPublicProfileSerializer(read_only=True)
    rated = UserPublicProfileSerializer(read_only=True)

    class Meta:
        model = Rating
        fields = [
            'id', 'trade', 'rater', 'rated',
            'score', 'comment', 'book_condition_accurate',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields
