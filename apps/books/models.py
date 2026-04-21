import uuid

from django.db import models


class Book(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    isbn_13 = models.CharField(max_length=13, unique=True, db_index=True)
    isbn_10 = models.CharField(max_length=10, null=True, blank=True, db_index=True)
    title = models.CharField(max_length=512)
    authors = models.JSONField(default=list)
    publisher = models.CharField(max_length=255, null=True, blank=True)
    publish_year = models.PositiveIntegerField(null=True, blank=True)
    cover_image_url = models.URLField(null=True, blank=True, max_length=500)
    cover_image_cached = models.CharField(max_length=500, null=True, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    physical_format = models.CharField(max_length=100, null=True, blank=True)
    subjects = models.JSONField(default=list)
    description = models.TextField(null=True, blank=True)
    open_library_key = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Book"
        verbose_name_plural = "Books"
        ordering = ["title"]

    def __str__(self):
        if isinstance(self.authors, list):
            authors_str = ", ".join(str(author) for author in self.authors[:2])
        elif isinstance(self.authors, str):
            authors_str = self.authors
        elif isinstance(self.authors, dict):
            authors_str = ", ".join(str(v) for v in list(self.authors.values())[:2]) or "Unknown"
        else:
            authors_str = "Unknown"
        return f"{self.title} by {authors_str} (ISBN-13: {self.isbn_13})"
