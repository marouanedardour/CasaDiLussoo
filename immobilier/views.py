from difflib import get_close_matches
from google.auth import default
from django.core.paginator import Paginator
import zipfile
import json
from django.core.files.uploadedfile import UploadedFile
from django.shortcuts import get_object_or_404, redirect, render
from django.core.files.base import ContentFile
from immobilier.forms import RegisterForm
from .models import Marque, MessageClient, Produit, ImageProduit 
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

@login_required(login_url='login') 
def home_view(request):
    category = request.GET.get('cat')
    marques = Marque.objects.all() 
    if category:
        produits = Produit.objects.filter(category=category) 
    else:
        produits = Produit.objects.all() 
    return render(request, 'home.HTML', {'produits': produits, 'marques': marques})

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