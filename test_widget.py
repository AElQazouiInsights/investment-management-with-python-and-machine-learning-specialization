import ipywidgets as widgets

# Simple test
def test_func(x):
    return x * 2

# Create interactive widget
widget_instance = widgets.interact(test_func, x=(0, 10, 1))

print("Widget created successfully")
print(f"Widget type: {type(widget_instance)}")
print(f"Widget has _model_id: {hasattr(widget_instance, '_model_id')}")
if hasattr(widget_instance, 'widget'):
    print(f"Widget.widget type: {type(widget_instance.widget)}")
    print(f"Widget.widget has _model_id: {hasattr(widget_instance.widget, '_model_id')}")