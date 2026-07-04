from django.db import models
import uuid

class Client(models.Model): 
    email = models.EmailField(unique=True)
    
    def __str__(self):
        return self.email
 
choix_list = [
    ('disponible', 'Disponible'),
    ('indisponible', 'Indisponible'),
]

class BienImmobilier(models.Model): 
    marque = models.ForeignKey('Marque', on_delete=models.CASCADE, related_name='biens', null=True, blank=True)
    statut = models.CharField(max_length=50, choices=choix_list, default='disponible')
    
    def is_available(self):
        return self.statut == 'disponible'
    
    def __str__(self):
        return f"bien {self.id} - {self.statut}"

class Commande(models.Model): 
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    bien = models.ForeignKey(BienImmobilier, on_delete=models.CASCADE)
    date_creation = models.DateTimeField(auto_now_add=True) 
    statut = models.CharField(max_length=50, choices=choix_list, default='disponible')
    
    def __str__(self):
        return f"Commande {self.id} for {self.client.email}"
    
class Marque(models.Model):
    nom = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='logos/')
    
    def __str__(self):
        return self.nom
    

CATEGORY_CHOICES = [
    ('bathroom', 'Bathroom'),
    ('kitchen', 'Kitchen'),
    ('furniture', 'Furniture'),
    ('lighting', 'Lighting'),
    ('materials', 'Materials'),
    ('wellness', 'Wellness'),
]

class Produit(models.Model):
    marque = models.ForeignKey('Marque', on_delete=models.CASCADE, related_name='produits')
    nom = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True, null=True, verbose_name="Catégorie")
    description = models.TextField()
    prix = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image_couverture = models.ImageField(upload_to='produits/couvertures/', null=True, blank=True)
    
    def __str__(self):
        return self.nom

class Review(models.Model):
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='reviews')
    nom_client = models.CharField(max_length=100) 
    commentaire = models.TextField() 
    date_creation = models.DateTimeField(auto_now_add=True) 
    
    def __str__(self):
        return f"Avis de {self.nom_client} sur {self.produit.nom}" 
    
class ImageProduit(models.Model):
    produit = models.ForeignKey(Produit, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='produits/')

    def __str__(self):
        return f"Image pour {self.produit.nom}"
    
class MessageClient(models.Model):
    produit = models.ForeignKey(Produit, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    nom = models.CharField(max_length=100)
    email = models.EmailField()
    tel = models.CharField(max_length=20)
    message = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Message de {self.nom} sur {self.produit.nom if self.produit else 'Général'}"
    
from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    USER_TYPES = (
        ('manager', 'Manager'),
        ('employee', 'Employee'),
        ('client', 'Client'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=20, choices=USER_TYPES)

    def __str__(self):
        return f"{self.user.username} - {self.user_type}"   
    
class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        if self.user:
            return f"Cart of {self.user.username}"
        return f"Guest Cart ({self.session_key})"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    def __str__(self):
        return self.produit.nom
    
from django.utils import timezone
import uuid

class Order(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    STATUS = (
        ("new", "New"),
        ("processing", "Processing"),
        ("completed", "Completed"),
    )
    reference = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
    )
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    message = models.TextField(blank=True)
    order_details = models.TextField()
    pdf = models.FileField(upload_to="orders/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        if not self.reference:
            today = timezone.now().strftime("%Y%m%d")
            self.reference = f"CDL-{today}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)
    def __str__(self):
        return self.reference
