from django.urls import path
from . import views
from .views import handle_chat_message

urlpatterns = [
    path('', views.home_view, name='home'), 
    path('produit/<int:produit_id>/', views.product_detail, name='product_detail'),
    path('contact/', views.contact_view, name='contact'),
    path('produit/<int:produit_id>/upload-zip/', views.upload_zip, name='upload_zip'),
    path('search/', views.smart_search, name='smart_search'),
    path('chatbot/', handle_chat_message, name='chatbot_response'),
    path('about/', views.about_view, name='about'),
    path('add-to-cart/<int:produit_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart_view, name='cart_view'),
    path('send-order/', views.send_order, name='send_order'),
    path('remove-from-cart/<int:image_id>/', views.remove_from_cart, name='remove_from_cart'),
    path("my-orders/", views.my_orders, name="my_orders"),
    path("my-orders/<int:order_id>/", views.order_detail, name="order_detail"),
]
