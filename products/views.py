from django.shortcuts import render, redirect
from django.http import HttpResponse

from ledger.models import TacoBank, TacoLedger
from products.models import Product, ProductAttributeStock
from ledger.tasks import redeem_tacos
from integration.clients import get_client
from integration.models import Team
from django.conf import settings
from django.contrib import messages
from .forms import ProductSizeForm



def product(request, product_id):
    product = Product.objects.filter(id=product_id).first()
    size_stock = product.attribute_stock.filter(attribute__attribute_base__name = 'Size', stock__gte = 1)
    form = ProductSizeForm()
    form.fields['size'].queryset = size_stock
    context = {'product': product, 'user': request.user,
               'day_limit': settings.MAX_PURCHASES_PER_DAY,
               'form': form if size_stock.count() else '',
               }
    if request.user.is_authenticated:
        account = TacoBank.objects.filter(user=request.user).first()
        context['taco_balance'] = account.total_tacos
        context['purchases_today'] = account.total_purchases_today
        context['display_spend_warning'] = context['day_limit'] is not None and account.total_purchases_today >= context['day_limit']
    else:
        context['taco_balance'] = context['day_limit'] = context['display_spend_warning'] = 0
    return render(request, 'products/base_product.html', context)


def get_image(request, product_id, filename):
    print(f"GETTING IMAGE: {filename}")
    product = Product.objects.get(id=product_id)
    image_data = product.image.open()
    return HttpResponse(image_data, content_type="image/gif")


def checkout(request, product_id):
    product = Product.objects.filter(id=product_id).first()
    size_param = request.GET.get('size')
    context = {'product': product,
               'user': request.user,
               'day_limit': settings.MAX_PURCHASES_PER_DAY,
               'size_str': f'?size={size_param}' if size_param else ""
               }
    if request.user.is_authenticated:
        account = TacoBank.objects.filter(user=request.user).first()
        context['taco_balance'] = account.total_tacos
        context['purchases_today'] = account.total_purchases_today
        context['display_spend_warning'] = context['day_limit'] is not None and account.total_purchases_today >= context['day_limit']
    else:
        context['taco_balance'] = context['day_limit'] = context['display_spend_warning'] = 0
    return render(request, 'products/checkout.html',
                  context=context)


def checkout_button(request, product_id):
    product = Product.objects.filter(id=product_id).first()
    user = request.user
    client = get_client(user.team_user.team)
    taco_bank = TacoBank.objects.filter(user=user)
    total_tacos = taco_bank.first().total_tacos
    purchased_size = request.GET.get('size')
    size = ''
    if purchased_size:
        size = ProductAttributeStock.objects.get(id=purchased_size).attribute.value
    if total_tacos >= product.price:
        redeem_tacos({"user_id": request.user.unique_id, "product_name": product.name, "amount": product.price, "receiver_id": user.team_user.team.bot_user_id, "tacos": product.price, "giver_id": request.user.unique_id}, team=user.team_user.team)
        client.order_information(user.unique_id, settings.ORDER_CHANNEL, product.name, size)
        client.receipt(user.unique_id, product.name, product.price, total_tacos-product.price)
        messages.success(request, f"Successfully purchased {product.name}!")
    else:
        messages.error(request, "Insufficient taco balance.")
        return render(request, 'products/checkout.html', context={'product': product})
    
    if purchased_size:
        size = ProductAttributeStock.objects.get(id=purchased_size)
        size.stock = size.stock - 1
        size.save()
    else:
        product.general_stock = (product.general_stock or 0) - 1
        product.save()
    return redirect('home-page')
