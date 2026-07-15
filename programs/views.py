from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.services.access import (
    get_client_or_404,
    is_administrator,
    is_coach,
)
from core.services.audit import record_change, record_form_changes
from coaching.services.clients import active_clients

from .forms import (
    AssignProgramForm,
    AssignProgramToClientForm,
    ProgramForm,
    ProgramWeekForm,
    WorkoutDayForm,
    WorkoutExerciseForm,
)
from .models import Program, ProgramWeek, WorkoutDayTemplate, WorkoutExercise
from .services.copying import copy_day, copy_program, copy_week


def _sync_program_weeks(program):
    program.weeks.filter(
        week_number__gt=program.number_of_weeks, days__isnull=True
    ).delete()
    existing = set(program.weeks.values_list("week_number", flat=True))
    ProgramWeek.objects.bulk_create([
        ProgramWeek(program=program, week_number=number)
        for number in range(1, program.number_of_weeks + 1)
        if number not in existing
    ])


def _refresh_assigned_schedule(program, changed_by):
    if program.assigned_to_id and program.status == Program.Status.ACTIVE:
        program.assign_to(
            program.assigned_to,
            assigned_by=changed_by,
            start_date=program.start_date,
        )


# ---------------------------------------------------------------- client view

@login_required
def my_program(request):
    """The athlete's read-only view of their full current plan."""
    program = (
        Program.objects.filter(assigned_to=request.user, status=Program.Status.ACTIVE)
        .prefetch_related("weeks__days__exercises__exercise")
        .first()
    )
    return render(request, "programs/my_program.html", {
        "program": program,
        "current_week": program.current_week_number() if program else None,
    })


# ------------------------------------------------------------- builder (coach)

def _require_program_access(user, program):
    if is_administrator(user):
        return
    if not (user.is_coach and program.owner_id == user.id):
        raise PermissionDenied


def _coach_only(user):
    if not is_coach(user):
        raise PermissionDenied


@login_required
def builder_list(request):
    _coach_only(request.user)
    if is_administrator(request.user):
        programs = Program.objects.all().select_related("assigned_to", "owner")
    else:
        programs = Program.objects.filter(owner=request.user).select_related("assigned_to")
    return render(request, "programs/builder_list.html", {"programs": programs})


@login_required
def builder_create(request):
    _coach_only(request.user)
    form = ProgramForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        program = form.save(commit=False)
        program.owner = request.user
        program.save()
        for number in range(1, program.number_of_weeks + 1):
            ProgramWeek.objects.create(program=program, week_number=number)
        messages.success(request, f"Program “{program.name}” created as a draft.")
        return redirect("programs:builder_detail", program_uuid=program.uuid)
    return render(request, "programs/builder_form.html", {"form": form, "program": None})


@login_required
def builder_detail(request, program_uuid):
    program = get_object_or_404(
        Program.objects.prefetch_related("weeks__days__exercises__exercise"),
        uuid=program_uuid,
    )
    _require_program_access(request.user, program)
    clients = active_clients(
        request.user, include_all_for_admin=True
    ).filter(is_athlete=True, is_active=True).order_by(
        "first_name", "last_name", "username"
    )
    assign_form = AssignProgramToClientForm(
        request.POST or None, clients=clients, program=program
    )
    if request.method == "POST" and assign_form.is_valid():
        client = assign_form.cleaned_data["client"]
        if program.assigned_to_id and program.assigned_to_id != client.id:
            assign_form.add_error(
                "client",
                "This program is already assigned to another client. Duplicate it first.",
            )
        else:
            program.assign_to(
                client,
                assigned_by=request.user,
                start_date=assign_form.cleaned_data["start_date"],
            )
            messages.success(
                request,
                f"Assigned “{program.name}” to {client.display_label} and created their schedule.",
            )
            return redirect("programs:builder_detail", program_uuid=program.uuid)
    return render(request, "programs/builder_detail.html", {
        "program": program,
        "assign_form": assign_form,
        "has_assignable_clients": clients.exists(),
    })


@login_required
def builder_edit(request, program_uuid):
    program = get_object_or_404(Program, uuid=program_uuid)
    _require_program_access(request.user, program)
    form = ProgramForm(request.POST or None, instance=program)
    if request.method == "POST" and form.is_valid():
        start_date_changed = "start_date" in form.changed_data
        duration_changed = "number_of_weeks" in form.changed_data
        record_form_changes(
            changed_by=request.user, affected_user=program.assigned_to,
            form=form, reason="Program edit",
        )
        program = form.save()
        _sync_program_weeks(program)
        if (start_date_changed or duration_changed) and program.assigned_to_id:
            # Keep the athlete profile and future calendar sessions aligned
            # with the coach-selected programme start date.
            program.assign_to(
                program.assigned_to,
                assigned_by=request.user,
                start_date=program.start_date,
            )
        messages.success(request, "Program updated.")
        return redirect("programs:builder_detail", program_uuid=program.uuid)
    return render(request, "programs/builder_form.html", {"form": form, "program": program})


@login_required
@require_POST
def builder_copy(request, program_uuid):
    program = get_object_or_404(Program, uuid=program_uuid)
    _require_program_access(request.user, program)
    clone = copy_program(program, owner=request.user)
    messages.success(request, f"Copied to draft “{clone.name}”.")
    return redirect("programs:builder_detail", program_uuid=clone.uuid)


@login_required
def builder_assign(request, program_uuid, client_uuid):
    program = get_object_or_404(Program, uuid=program_uuid)
    _require_program_access(request.user, program)
    client = get_client_or_404(request.user, client_uuid, manage=True)
    form = AssignProgramForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if program.assigned_to_id and program.assigned_to_id != client.id:
            messages.error(
                request,
                "This program is already assigned to another client. Duplicate it before assigning.",
            )
            return redirect("programs:builder_detail", program_uuid=program.uuid)
        program.assign_to(client, assigned_by=request.user,
                          start_date=form.cleaned_data["start_date"])
        messages.success(request, f"Assigned “{program.name}” to {client.display_label}.")
        return redirect("programs:builder_detail", program_uuid=program.uuid)
    return render(request, "programs/builder_assign.html", {
        "program": program, "client": client, "form": form,
    })


@login_required
def week_edit(request, week_id):
    week = get_object_or_404(ProgramWeek.objects.select_related("program"), pk=week_id)
    _require_program_access(request.user, week.program)
    form = ProgramWeekForm(request.POST or None, instance=week)
    if request.method == "POST" and form.is_valid():
        form.save()
        _refresh_assigned_schedule(week.program, request.user)
        messages.success(request, f"Week {week.week_number} updated.")
        return redirect("programs:builder_detail", program_uuid=week.program.uuid)
    return render(request, "programs/week_form.html", {"form": form, "week": week})


@login_required
@require_POST
def week_copy(request, week_id):
    """Copy a week's days/exercises into the next empty week (or append one)."""
    week = get_object_or_404(ProgramWeek.objects.select_related("program"), pk=week_id)
    program = week.program
    _require_program_access(request.user, program)
    next_number = (program.weeks.order_by("-week_number").first().week_number or 0) + 1
    copy_week(week, program, next_number)
    if next_number > program.number_of_weeks:
        program.number_of_weeks = next_number
        program.save(update_fields=["number_of_weeks", "updated_at"])
    _refresh_assigned_schedule(program, request.user)
    messages.success(request, f"Week {week.week_number} copied to week {next_number}.")
    return redirect("programs:builder_detail", program_uuid=program.uuid)


@login_required
def day_create(request, week_id):
    week = get_object_or_404(ProgramWeek.objects.select_related("program"), pk=week_id)
    _require_program_access(request.user, week.program)
    next_day = (week.days.count() or 0) + 1
    form = WorkoutDayForm(request.POST or None, initial={"day_number": next_day, "order": next_day})
    if request.method == "POST" and form.is_valid():
        day = form.save(commit=False)
        day.program_week = week
        day.save()
        _refresh_assigned_schedule(week.program, request.user)
        messages.success(request, f"Day “{day.name}” added.")
        return redirect("programs:builder_detail", program_uuid=week.program.uuid)
    return render(request, "programs/day_form.html", {"form": form, "week": week, "day": None})


@login_required
def day_edit(request, day_id):
    day = get_object_or_404(
        WorkoutDayTemplate.objects.select_related("program_week__program"), pk=day_id
    )
    program = day.program_week.program
    _require_program_access(request.user, program)
    form = WorkoutDayForm(request.POST or None, instance=day)
    if request.method == "POST" and form.is_valid():
        form.save()
        _refresh_assigned_schedule(program, request.user)
        messages.success(request, "Workout day updated.")
        return redirect("programs:builder_detail", program_uuid=program.uuid)
    return render(request, "programs/day_form.html", {
        "form": form, "week": day.program_week, "day": day,
    })


@login_required
@require_POST
def day_copy(request, day_id):
    day = get_object_or_404(
        WorkoutDayTemplate.objects.select_related("program_week__program"), pk=day_id
    )
    program = day.program_week.program
    _require_program_access(request.user, program)
    clone = copy_day(day, day.program_week, day_number=day.program_week.days.count() + 1)
    clone.name = f"{clone.name} (copy)"
    clone.save(update_fields=["name"])
    _refresh_assigned_schedule(program, request.user)
    messages.success(request, "Workout day copied.")
    return redirect("programs:builder_detail", program_uuid=program.uuid)


@login_required
@require_POST
def day_delete(request, day_id):
    day = get_object_or_404(
        WorkoutDayTemplate.objects.select_related("program_week__program"), pk=day_id
    )
    program = day.program_week.program
    _require_program_access(request.user, program)
    day.delete()
    _refresh_assigned_schedule(program, request.user)
    messages.success(request, "Workout day removed.")
    return redirect("programs:builder_detail", program_uuid=program.uuid)


@login_required
def exercise_create(request, day_id):
    day = get_object_or_404(
        WorkoutDayTemplate.objects.select_related("program_week__program"), pk=day_id
    )
    program = day.program_week.program
    _require_program_access(request.user, program)
    form = WorkoutExerciseForm(
        request.POST or None,
        initial={"order": day.exercises.count() + 1},
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        prescription = form.save(commit=False)
        prescription.workout_day = day
        prescription.save()
        record_change(
            changed_by=request.user, affected_user=program.assigned_to,
            obj=prescription, field="prescription",
            previous="", new=f"added {prescription.exercise.name}",
            reason="Workout prescription change",
        )
        _refresh_assigned_schedule(program, request.user)
        messages.success(request, f"{prescription.exercise.name} added to {day.name}.")
        return redirect("programs:builder_detail", program_uuid=program.uuid)
    return render(request, "programs/exercise_form.html", {
        "form": form, "day": day, "prescription": None,
    })


@login_required
def exercise_edit(request, exercise_uuid):
    prescription = get_object_or_404(
        WorkoutExercise.objects.select_related(
            "workout_day__program_week__program", "exercise"
        ),
        uuid=exercise_uuid,
    )
    program = prescription.workout_day.program_week.program
    _require_program_access(request.user, program)
    form = WorkoutExerciseForm(
        request.POST or None, instance=prescription, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        record_form_changes(
            changed_by=request.user, affected_user=program.assigned_to,
            form=form, reason="Workout prescription change",
        )
        form.save()
        _refresh_assigned_schedule(program, request.user)
        messages.success(request, "Prescription updated.")
        return redirect("programs:builder_detail", program_uuid=program.uuid)
    return render(request, "programs/exercise_form.html", {
        "form": form, "day": prescription.workout_day, "prescription": prescription,
    })


@login_required
@require_POST
def exercise_delete(request, exercise_uuid):
    prescription = get_object_or_404(
        WorkoutExercise.objects.select_related(
            "workout_day__program_week__program", "exercise"
        ),
        uuid=exercise_uuid,
    )
    program = prescription.workout_day.program_week.program
    _require_program_access(request.user, program)
    record_change(
        changed_by=request.user, affected_user=program.assigned_to,
        obj=prescription, field="prescription",
        previous=prescription.exercise.name, new="removed",
        reason="Workout prescription change",
    )
    prescription.delete()
    _refresh_assigned_schedule(program, request.user)
    messages.success(request, "Exercise removed.")
    return redirect("programs:builder_detail", program_uuid=program.uuid)


@login_required
@require_POST
def exercise_move(request, exercise_uuid, direction):
    prescription = get_object_or_404(
        WorkoutExercise.objects.select_related("workout_day__program_week__program"),
        uuid=exercise_uuid,
    )
    program = prescription.workout_day.program_week.program
    _require_program_access(request.user, program)
    siblings = list(prescription.workout_day.exercises.all())
    index = next(i for i, item in enumerate(siblings) if item.pk == prescription.pk)
    target = index - 1 if direction == "up" else index + 1
    if 0 <= target < len(siblings):
        siblings[index], siblings[target] = siblings[target], siblings[index]
        for position, item in enumerate(siblings, start=1):
            item.order = position
        WorkoutExercise.objects.bulk_update(siblings, ["order"])
    return redirect("programs:builder_detail", program_uuid=program.uuid)
