from django.db import models
from django.utils.text import slugify

class Card(models.Model):
    name = models.CharField(max_length=255, db_index=True, verbose_name='Nombre de la Carta')
    clean_name = models.CharField(max_length=255, db_index=True, blank=True, verbose_name='Nombre Limpio')
    ygoprodeck_id = models.PositiveIntegerField(unique=True, null=True, blank=True, db_index=True, verbose_name='ID YGOPRODeck')
    card_type = models.CharField(max_length=100, blank=True, verbose_name='Tipo de Carta')  # Monster, Spell, Trap
    human_readable_card_type = models.CharField(max_length=100, blank=True, verbose_name='Subtipo') # Effect Monster, Normal, etc.
    description = models.TextField(blank=True, verbose_name='Efecto / Descripción')
    race = models.CharField(max_length=100, blank=True, verbose_name='Raza / Tipo') # Dragon, Spellcaster, Continuous, etc.
    attribute = models.CharField(max_length=50, blank=True, verbose_name='Atributo') # DARK, LIGHT, etc.
    atk = models.IntegerField(null=True, blank=True, verbose_name='ATK')
    def_points = models.IntegerField(null=True, blank=True, verbose_name='DEF')
    level = models.IntegerField(null=True, blank=True, verbose_name='Nivel / Rango')
    scale = models.IntegerField(null=True, blank=True, verbose_name='Escala de Péndulo')
    link_val = models.IntegerField(null=True, blank=True, verbose_name='Rating de Enlace')
    archetype = models.CharField(max_length=150, blank=True, verbose_name='Arquetipo')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Carta'
        verbose_name_plural = 'Cartas'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.clean_name:
            self.clean_name = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class CardPrint(models.Model):
    class Edition(models.TextChoices):
        FIRST_EDITION = '1ST', '1st Edition'
        UNLIMITED = 'UNL', 'Unlimited'
        LIMITED = 'LIM', 'Limited Edition'

    class Language(models.TextChoices):
        EN = 'EN', 'Inglés'
        ES = 'ES', 'Español'
        JP = 'JP', 'Japonés'
        FR = 'FR', 'Francés'
        DE = 'DE', 'Alemán'
        IT = 'IT', 'Italiano'
        PT = 'PT', 'Portugués'
        KO = 'KO', 'Coreano'

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='prints', verbose_name='Carta Base')
    print_code = models.CharField(max_length=50, db_index=True, verbose_name='Código de Impresión') # Ej: LOB-001, RA01-EN001
    set_name = models.CharField(max_length=200, db_index=True, verbose_name='Nombre de la Expansión')
    rarity = models.CharField(max_length=100, verbose_name='Rareza') # Secret Rare, Ultra Rare, Common
    rarity_code = models.CharField(max_length=20, blank=True, verbose_name='Código de Rareza') # ScR, UR, C
    edition = models.CharField(max_length=10, choices=Edition.choices, default=Edition.FIRST_EDITION, verbose_name='Edición')
    language = models.CharField(max_length=5, choices=Language.choices, default=Language.EN, verbose_name='Idioma')
    
    image_url = models.URLField(max_length=500, blank=True, verbose_name='URL de Imagen Externa')
    image = models.ImageField(upload_to='card_prints/', blank=True, null=True, verbose_name='Imagen Local')
    tcgplayer_product_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name='TCGplayer Product ID')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Impresión de Carta'
        verbose_name_plural = 'Impresiones de Cartas'
        constraints = [
            models.UniqueConstraint(
                fields=['card', 'print_code', 'rarity', 'edition', 'language'],
                name='unique_card_print'
            )
        ]
        ordering = ['print_code', 'rarity']

    def __str__(self) -> str:
        return f"{self.card.name} [{self.print_code}] ({self.rarity} - {self.get_edition_display()} - {self.language})"
