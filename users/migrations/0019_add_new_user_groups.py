from django.db import migrations


def rename_salesperson_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    salesperson_group = Group.objects.get(name="salesperson")
    salesperson_group.name = "django_salesperson"
    salesperson_group.save()


def revert_rename_salesperson_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    salesperson_group = Group.objects.get(name="django_salesperson")
    salesperson_group.name = "salesperson"
    salesperson_group.save()


def add_new_user_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.create(name="drupal_salesperson")
    Group.objects.create(name="staff")


def remove_new_user_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="drupal_salesperson").delete()
    Group.objects.filter(name="staff").delete()


def assign_old_users_to_new_groups(apps, schema_editor):
    # Part of old users will be added to "django_salesperson" group
    # The rest will be moved to "drupal_salesperson" group if they have a Profile
    Group = apps.get_model("auth", "Group")
    drupal_group = Group.objects.get(name="drupal_salesperson")
    django_group = Group.objects.get(name="django_salesperson")
    drupal_salesperson_users = django_group.user_set.exclude(profile=None)
    drupal_group.user_set.add(*drupal_salesperson_users)
    django_group.user_set.remove(*drupal_salesperson_users)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0018_disable_profile_email_validation"),
    ]

    operations = [
        migrations.RunPython(rename_salesperson_group, revert_rename_salesperson_group),
        migrations.RunPython(add_new_user_groups, remove_new_user_groups),
        migrations.RunPython(assign_old_users_to_new_groups, migrations.RunPython.noop),
    ]
