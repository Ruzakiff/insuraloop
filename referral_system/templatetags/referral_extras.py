from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Gets a dictionary item by key"""
    return dictionary.get(key, '') 