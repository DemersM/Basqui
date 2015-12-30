from django import template

register = template.Library()

@register.simple_tag
def active(request, pattern):
    import re
    if re.search(pattern, request.path):
        return 'active'
    return ''


"""
filters for checking the type of objects and formfields

Usage:

{% if form|obj_type:'mycustomform' %}
  <form class="custom" action="">
{% else %}
  <form action="">
{% endif %}


{% if field|field_type:'checkboxinput' %}
  <label class="cb_label">{{ field }} {{ field.label }}</label>
{% else %}
  <label for="id_{{ field.name }}">{{ field.label }}</label> {{ field }}
{% endif %}

"""

@register.filter(name='check_type')
def check_type(obj, className):
    try:
        t = obj.__class__.__name__
        return t.lower() == str(className).lower()
    except:
        pass
    return False


@register.filter(name='field_type')
def field_type(obj, className):
    return check_type(obj, className)
