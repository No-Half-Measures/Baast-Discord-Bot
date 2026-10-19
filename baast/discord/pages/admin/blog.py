import uuid, os
from asgiref.sync import async_to_sync

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from app.models import Blog
from django.utils.text import slugify
from discord.models import User
from django.core.files.storage import default_storage
from django.utils.html import strip_tags
from django.utils.text import Truncator

from channels.layers import get_channel_layer

@login_required
def blog_list(request):
    posts = Blog.objects.all().order_by('-created_at')
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'post_types': dict(Blog.POST_TYPE_CHOICES)
    }
    return render(request, 'discord/pages/admin/blog/list.html', context)

@login_required
def blog_create(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        post_type = request.POST.get('post_type')
        is_published = request.POST.get('is_published') == 'on'
        push_to_discord = request.POST.get('push_to_discord') == 'on'
        
        post = Blog.objects.create(
            title=title,
            content=content,
            post_type=post_type,
            is_published=is_published,
            author=request.user.id  # Store the Discord user ID directly
        )
        
        if 'featured_image' in request.FILES:
            post.featured_image = request.FILES['featured_image']
            post.save()
        
        if push_to_discord:
            truncator = Truncator(strip_tags(content))
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.send)('discord', {
                                                    'type': 'post.blog.post',
                                                    'url': f'https://baast.app/post/{post.slug}',
                                                    'title': title,
                                                    'description': truncator.words(30)
                                                })
            
        return redirect('discord:admin_blog_list')
        
    context = {
        'post_types': dict(Blog.POST_TYPE_CHOICES)
    }
    return render(request, 'discord/pages/admin/blog/create.html', context)

@login_required
def blog_edit(request, slug):
    post = get_object_or_404(Blog, slug=slug)
    
    if request.method == 'POST':
        post.title = request.POST.get('title')
        post.content = request.POST.get('content')
        post.post_type = request.POST.get('post_type')
        post.is_published = request.POST.get('is_published') == 'on'
        
        if 'featured_image' in request.FILES:
            post.featured_image = request.FILES['featured_image']
            
        post.save()
        
        return redirect('discord:admin_blog_list')
        
    context = {
        'post': post,
        'post_types': dict(Blog.POST_TYPE_CHOICES)
    }
    return render(request, 'discord/pages/admin/blog/edit.html', context)

@login_required
def blog_delete(request, slug):
    post = get_object_or_404(Blog, slug=slug)
    
    if request.method == 'POST':
        post.delete()
        return JsonResponse({'status': 'success'})
        
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def upload_image(request):
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']
        
        # Generate unique filename
        file_extension = os.path.splitext(uploaded_file.name)[1]
        filename = f"editor_images/{uuid.uuid4()}{file_extension}"
        
        # Save the file
        file_path = default_storage.save(filename, uploaded_file)
        file_url = default_storage.url(file_path)
        
        return JsonResponse({'location': file_url})
    
    return JsonResponse({'error': 'Invalid request'}, status=400) 