from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from .models import Commande, Produit, ImageProduit, Marque, BienImmobilier, Client, Review, MessageClient
from .views import upload_zip 

admin.site.register(BienImmobilier)
admin.site.register(Client)
admin.site.register(Commande)
admin.site.register(Marque)
admin.site.register(Review)
admin.site.register(MessageClient)

class ImageProduitInline(admin.TabularInline):
    model = ImageProduit
    extra = 0

@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    inlines = [ImageProduitInline] 
    change_form_template = 'admin/produit_change_form.html' 

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:produit_id>/upload-zip/', self.admin_site.admin_view(self.upload_zip_redirect), name='produit-upload-zip'),
        ]
        return custom_urls + urls

    def upload_zip_redirect(self, request, produit_id):
        return upload_zip(request, produit_id)
    
from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type')
    list_filter = ('user_type',) 

from django.contrib import admin
from .models import Order
from django.utils.html import format_html

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "full_name",
        "phone_number",
        "created_at",
    )
    readonly_fields = (
        "reference",
        "created_at",
        "download_pdf",
    )
    fields = (
        "reference",
        ("full_name", "phone_number"),
        "email",
        "message",
        "order_details",
        "pdf",
        "created_at",
        "download_pdf",
    )
    def download_pdf(self, obj):
        if obj.pdf:
            return format_html(
                '<a class="button" href="{}" target="_blank">📄 Download Order PDF</a>',
                obj.pdf.url
            )
        return "No PDF"
    download_pdf.short_description = "Order File"
    