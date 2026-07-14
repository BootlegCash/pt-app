from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Exercise


@login_required
def library(request):
    exercises = Exercise.objects.filter(active=True, public=True)
    query = request.GET.get("q", "").strip()
    muscle = request.GET.get("muscle", "")
    category = request.GET.get("category", "")
    if query:
        exercises = exercises.filter(Q(name__icontains=query))
    if muscle:
        exercises = exercises.filter(primary_muscle=muscle)
    if category:
        exercises = exercises.filter(exercise_category=category)
    return render(request, "exercises/library.html", {
        "exercises": exercises,
        "query": query,
        "muscle": muscle,
        "category": category,
        "muscles": Exercise.Muscle.choices,
        "categories": Exercise.Category.choices,
    })


@login_required
def detail(request, slug):
    exercise = get_object_or_404(Exercise, slug=slug, active=True, public=True)
    return render(request, "exercises/detail.html", {"exercise": exercise})
