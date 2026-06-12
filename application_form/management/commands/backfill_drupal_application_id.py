import csv

from django.core.management.base import BaseCommand, CommandError

from application_form.models import Application


class Command(BaseCommand):
    """
    Populate Application.drupal_application_id from a CSV export provided by Drupal.

    The CSV must have columns: uuid,nid
    where uuid matches Application.external_uuid and nid is the Drupal node ID.
    """

    help = "Backfill drupal_application_id on Application from a CSV file (uuid,nid)"

    def add_arguments(self, parser):
        """
        Register command arguments.

                Parameters:
                        parser: ArgumentParser instance
        """
        parser.add_argument(
            "--csv",
            required=True,
            help="Path to CSV file with columns: uuid,nid",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing to the database",
        )

    def handle(self, *args, **options):
        """
        Execute the backfill.

                Parameters:
                        args: positional arguments (unused)
                        options (dict): parsed command options including csv path and dry_run flag
        """
        csv_path = options["csv"]
        dry_run = options["dry_run"]

        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if "uuid" not in (reader.fieldnames or []) or "nid" not in (
                    reader.fieldnames or []
                ):
                    raise CommandError(
                        f"CSV must have columns 'uuid' and 'nid', "
                        f"got: {reader.fieldnames}"
                    )
                rows = list(reader)
        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {csv_path}")

        self.stdout.write(f"Read {len(rows)} rows from {csv_path}")

        updated = 0
        skipped_no_match = 0
        skipped_already_set = 0

        for row in rows:
            uuid = row["uuid"].strip()
            try:
                nid = int(row["nid"].strip())
            except ValueError:
                self.stderr.write(f"Skipping row with invalid nid: {row}")
                continue

            try:
                app = Application.objects.get(external_uuid=uuid)
            except Application.DoesNotExist:
                self.stderr.write(
                    f"No Application found for uuid={uuid}, skipping"
                )
                skipped_no_match += 1
                continue

            if app.drupal_application_id is not None:
                if app.drupal_application_id == nid:
                    skipped_already_set += 1
                    continue
                self.stdout.write(
                    f"Application id={app.id} already has "
                    f"drupal_application_id={app.drupal_application_id}, "
                    f"would overwrite with nid={nid}"
                )

            if dry_run:
                self.stdout.write(
                    f"[dry-run] Would set Application id={app.id} "
                    f"drupal_application_id={nid}"
                )
            else:
                app.drupal_application_id = nid
                app.save(update_fields=["drupal_application_id"])
                self.stdout.write(
                    f"Set Application id={app.id} drupal_application_id={nid}"
                )
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{'[dry-run] ' if dry_run else ''}"
                f"Done: updated={updated}, "
                f"skipped_no_match={skipped_no_match}, "
                f"skipped_already_set={skipped_already_set}"
            )
        )
