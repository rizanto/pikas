# =============================================================================
# PIKAS — Performance Indicators Knowledgebase Accountability System
# File    : decorators.py
# Author  : Ilham Rizanto
# Copyright (c) 2026 Ilham Rizanto. All Rights Reserved.
# Unauthorized use, reproduction, or distribution is strictly prohibited.
# See LICENSE file for full terms.
# =============================================================================
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from functools import wraps

def role_required(allowed_roles):
    """
    Decorator for views that checks that the user is logged in and has the given role.
    allowed_roles should be a list of strings (e.g. ['ADMIN', 'OPERATOR'])
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
                
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
                
            if request.user.role not in allowed_roles:
                # Optionally set a flash message here
                return redirect('dashboard')
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
