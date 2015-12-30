from django import forms
from layers.models import *

class AttributeValueForm(forms.ModelForm):
    class Meta:
        model = AttributeValue


