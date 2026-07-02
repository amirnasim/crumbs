from django.db import models
from django.utils.text import slugify


def category_image_path(instance, filename):
    return f"categories/{instance.slug}/{filename}"


def product_image_path(instance, filename):
    return f"products/{instance.category.slug}/{instance.slug}/{filename}"


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, db_index=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to=category_image_path, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"/shop/{self.slug}/"


class Product(models.Model):
    class AvailabilityStatus(models.TextChoices):
        AVAILABLE = "available", "Available"
        OUT_OF_STOCK = "out_of_stock", "Out of Stock"
        COMING_SOON = "coming_soon", "Coming Soon"

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    name = models.CharField("نام محصول", max_length=200)
    slug = models.SlugField("نامک", max_length=220, db_index=True)
    description = models.TextField("توضیحات")
    ingredients = models.TextField("مواد اولیه", blank=True)
    price = models.DecimalField("قیمت", max_digits=10, decimal_places=2)
    image = models.ImageField("تصویر", upload_to=product_image_path, blank=True)
    availability_status = models.CharField(
        "وضعیت موجودی",
        max_length=20,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.AVAILABLE,
        db_index=True,
    )
    is_featured = models.BooleanField("ویژه", default=False, db_index=True)
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین بروزرسانی", auto_now=True)

    class Meta:
        ordering = ["-is_featured", "name"]
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
        constraints = [
            models.UniqueConstraint(
                fields=["category", "slug"],
                name="unique_product_slug_per_category",
            )
        ]
        indexes = [
            models.Index(fields=["category", "slug"]),
            models.Index(fields=["is_featured", "availability_status"]),
        ]

    def __str__(self):
        return self.name

    @property
    def is_available(self):
        return self.availability_status == self.AvailabilityStatus.AVAILABLE

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"/shop/{self.category.slug}/{self.slug}/"
