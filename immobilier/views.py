from django.utils import timezone
from reportlab.platypus import Table, TableStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Image
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
import os
from django.contrib import admin
from annotated_types import doc
from httpcore import request
from reportlab.lib import styles
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from django.core.files.base import ContentFile
from io import BytesIO
from django.core.mail import EmailMessage
import io
from difflib import get_close_matches
from google.auth import default
from django.core.paginator import Paginator
import zipfile
import json
from django.core.files.uploadedfile import UploadedFile
from django.shortcuts import get_object_or_404, redirect, render
from django.core.files.base import ContentFile
from immobilier.forms import RegisterForm
from .models import Marque, MessageClient, Order, Produit, ImageProduit 
from django.contrib import messages
from django.db.models import Q
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators  import login_required
from django.contrib.auth.forms import UserCreationForm
from django import forms
from groq import Groq
from random import sample
from .models import Cart, CartItem, Produit


def upload_zip(request, produit_id):
    produit = get_object_or_404(Produit, pk=produit_id)
    if request.method == 'POST' and request.FILES.get('zip_file'):
        zip_file:UploadedFile = request.FILES['zip_file']
        if not zip_file.name.endswith('.zip'):
            messages.error(request, "Veuillez télécharger un fichier valide au format .zip")
            return redirect(f'/admin/immobilier/produit/{produit.id}/change/')
        try:
            with zipfile.ZipFile(zip_file, 'r') as z:
                for filename in z.namelist():
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                        img_data = z.read(filename)
                        image_obj = ImageProduit(produit=produit)
                        image_obj.image.save(filename, ContentFile(img_data))
            messages.success(request, f"Images importées avec succès pour {produit.nom}")
        except zipfile.BadZipFile:
            messages.error(request, "Le fichier est corrompu ou n'est pas un zip valide.")
        except Exception as e:
            messages.error(request, f"Erreur: {e}")
        return redirect(f'/admin/immobilier/produit/{produit.id}/change/')      
    return render(request, 'upload_zip.html', {'produit': produit})

def product_detail(request, produit_id): 
    produit = get_object_or_404(Produit, id=produit_id)
    images_list = produit.images.all()
    paginator = Paginator(images_list, 25) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'product_detail.html', {
        'produit': produit,
        'page_obj': page_obj
    })

def contact_view(request):
    if request.method == 'POST':
        MessageClient.objects.create(
            nom=request.POST.get('name'),
            email=request.POST.get('email'),
            tel=request.POST.get('phone'),
            message=request.POST.get('message')
        )
        messages.success(request, "Votre message a été envoyé!")
        return redirect('home')
    return render(request, 'contact.html')


def smart_search(request):
    query = request.GET.get('q', '').strip().lower()
    produits = Produit.objects.filter(
        Q(nom__icontains=query) | 
        Q(category__icontains=query) 
    ).distinct()
    
    if query:
        produits = Produit.objects.filter(Q(nom__icontains=query) | Q(description__icontains=query))
        if not produits.exists():
            all_names = Produit.objects.values_list('nom', flat=True)
            matches = get_close_matches(query, list(all_names), n=3, cutoff=0.6)
            if matches:
                produits = Produit.objects.filter(nom__in=matches)
                
    marques = Marque.objects.all() 
    return render(request, 'search_results.html', { 
        'produits': produits,
        'marques': marques,
        'query': query
    })


client = Groq(api_key=settings.GROQ_API_KEY)

def handle_chat_message(request):
    data = json.loads(request.body)
    messages_history = data.get('messages', [])
    lang = data.get('lang', 'fr')
    user_message = messages_history[-1]['content'] if messages_history else ""
    if not user_message:
        return JsonResponse({"reply": "Veuillez écrire un message."})
    produits = list(Produit.objects.order_by('?')[:10])

    if len(produits) > 15:
        produits = sample(produits, 15)
    catalogue=""
    for p in produits:
        image_url = ""
        if p.image_couverture:
            image_url = request.build_absolute_uri(
                p.image_couverture.url
            )
        product_url = request.build_absolute_uri(
            f'/produit/{p.id}/'
        )
        catalogue += f"""
    Produit:
    {p.nom}
    Description:
    {p.description}
    IMAGE_URL:
    {image_url}
    PRODUCT_URL:
    {product_url}
    """
    system = f"""
You are the luxury sales assistant of Casa Di Lusso.
STRICT RULES:
LANGUAGE:
- Always answer in the same language as the customer.
- Never change the customer's language.
STYLE:
- Maximum 3 short lines.
- Never write long explanations.
- Be professional and elegant.
PRODUCTS:
- Only show product images when the customer explicitly asks for:
  product, recommendation, collection, photos, images, suggestions.
WHEN SHOWING PRODUCTS:
You MUST use ONLY this format:
IMAGE:URL_IMAGE|LINK:URL_PRODUCT
Do not add any words before or after this format.
NEVER write:
- raw links
- URLs
- "visit this link"
- IMAGE_URL
- PRODUCT_URL
GENERAL QUESTIONS:
Answer normally without IMAGE or LINK.
Catalog:
{catalogue}
"""
    conversation = [{"role": "system", "content": system}] + messages_history    
    try:
        result = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=conversation,
            temperature=0.7 
        )
        return JsonResponse({
            "reply": result.choices[0].message.content
        })
    except Exception as e:
        return JsonResponse({"reply": str(e)})
    
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home') 
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def home_view(request):
    category = request.GET.get('cat')
    marques = Marque.objects.all() 
    if category:
        produits = Produit.objects.filter(category=category) 
    else:
        produits = Produit.objects.all() 
    return render(request, 'home.html', {'produits': produits, 'marques': marques})

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            return redirect('login')
    else:
        form = RegisterForm()
    
    return render(request, 'register.html', {'form': form})

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    telephone = forms.CharField(max_length=20, required=True)

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email', 'telephone')



def search_api(request):
    query = request.GET.get('q', '').strip().lower()
    all_products = Produit.objects.all()
    names = [p.nom.lower() for p in all_products]
    matches = get_close_matches(query, names, n=5, cutoff=0.4)
    results = Produit.objects.filter(nom__icontains=query) | Produit.objects.filter(nom__in=matches)
    
    data = [{"nom": p.nom, "url": f"/produit/{p.id}/", "img": p.image_couverture.url if p.image_couverture else ""} for p in results[:5]]
    return JsonResponse(data, safe=False)


def logout_view(request):
    logout(request)
    return redirect('home') 

def about_view(request):
    return render(request, 'about.html')

def cart_view(request):
    cart_ids = request.session.get("cart", [])
    cart_items = ImageProduit.objects.filter(
        id__in=cart_ids
    ).select_related(
        "produit__marque"
    )
    print("SESSION =", cart_ids)
    print("IMAGES =", list(cart_items.values_list("id", flat=True)))
    return render(
        request,
        "cart.HTML",
        {
            "cart_items": cart_items
        }
    )
    
def send_order(request):
    if request.method == "POST":
        full_name = request.POST.get("nom")
        email = request.POST.get("email")
        phone = request.POST.get("tel")
        message = request.POST.get("message", "")
        cart_ids = request.session.get("cart", [])
        images = ImageProduit.objects.filter(
            id__in=cart_ids
        ).select_related(
            "produit__marque"
        )
        order_details = ""
        for image in images:
            product = image.produit
            order_details += (
                f"Brand: {product.marque.nom}\n"
                f"Product: {product.nom}\n"
                "-----------------------------\n"
            )
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            full_name=full_name,
            email=email,
            phone_number=phone,
            message=message,
            order_details=order_details,
        )
        order.refresh_from_db()
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )
        story = []
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "TitleLuxury",
            parent=styles["Heading1"],
            alignment=TA_CENTER,
            textColor=HexColor("#b08d57"),
            fontSize=24,
            spaceAfter=20,
        )
        subtitle = ParagraphStyle(
            "Sub",
            parent=styles["Heading2"],
            textColor=HexColor("#444444"),
        )
        normal = styles["Normal"]
        logo_path = os.path.join(
            settings.BASE_DIR,
            "static",
            "images",
            "logo.png"
        )
        if os.path.exists(logo_path):
            logo = Image(logo_path)
            logo.drawHeight = 3 * cm
            logo.drawWidth = 3 * cm
            logo.hAlign = "CENTER"
            story.append(logo)
        story.append(
            Paragraph(
                "<b>Casa Di Lusso</b>",
                title
            )
        )
        story.append(
            Paragraph(
                "Quotation Request",
                subtitle
            )
        )
        story.append(Spacer(1, 0.5 * cm))
        date = order.created_at or timezone.now()
        story.append(
            Paragraph(
                f"<b>Date:</b> {date.strftime('%d/%m/%Y %H:%M')}",
                normal
            )
        )
        story.append(Spacer(1, 0.5 * cm))
        story.append(
            Paragraph("<b>Client Information</b>", subtitle)
        )
        story.append(
            Paragraph(f"Name : {order.full_name}", normal)
        )
        story.append(
            Paragraph(f"Email : {order.email}", normal)
        )
        story.append(
            Paragraph(f"Phone : {order.phone_number}", normal)
        )
        story.append(Spacer(1, 0.5 * cm))
        story.append(
            Paragraph("<b>Client Message</b>", subtitle)
        )
        story.append(
            Paragraph(
                order.message or "No message",
                normal
            )
        )
        story.append(Spacer(1, 1 * cm))
        story.append(
            Paragraph(
                "<b>Selected Products</b>",
                subtitle
            )
        )
        story.append(Spacer(1, 0.5 * cm))
        brand_style = ParagraphStyle(
            "Brand",
            parent=normal,
            alignment=TA_CENTER,
            textColor=HexColor("#b08d57"),
            fontSize=11,
        )
        table_data = []
        row = []
        for image in images:
            product = image.produit
            elements = []
            if os.path.exists(image.image.path):
                img = Image(image.image.path)
                img.drawWidth = 5 * cm
                img.drawHeight = 5 * cm
                elements.append(img)
            elements.append(
                Paragraph(
                    f"<b>{product.marque.nom}</b>",
                    brand_style
                )
            )
            row.append(elements)
            if len(row) == 3:
                table_data.append(row)
                row = []
        if row:
            while len(row) < 3:
                row.append("")
            table_data.append(row)
        table = Table(
            table_data,
            colWidths=[6 * cm, 6 * cm, 6 * cm]
        )
        table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 15),
        ]))
        story.append(table)
        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        order.pdf.save(
            f"{order.reference}.pdf",
            ContentFile(pdf),
            save=False
        )
        order.save()
        request.session["cart"] = []
        request.session.modified = True
        messages.success(request, "Your request has been sent successfully.")
        return redirect("home")
    
def add_to_cart(request, produit_id):
    cart = request.session.get("cart", [])
    if produit_id not in cart:
        cart.append(produit_id)
    request.session["cart"] = cart
    request.session.modified = True
    print("CART =", request.session["cart"])   
    return JsonResponse({
        "status": "success",
        "count": len(cart)
    })

def remove_from_cart(request, image_id):
    cart = request.session.get("cart", [])
    if image_id in cart:
        cart.remove(image_id)
    request.session["cart"] = cart
    request.session.modified = True
    return redirect("cart_view")

@login_required
def my_orders(request):
    orders = Order.objects.filter(
        user=request.user
    ).order_by("-created_at")
    return render(
        request,
        "my_orders.html",
        {
            "orders": orders
        }
    )    

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user
    )
    return render(
        request,
        "order_detail.html",
        {
            "order": order
        }
    ) 