from django.core.management.base import BaseCommand

from recruitment.models import Skill, SkillAlias
from recruitment.services.ats import DEFAULT_SKILL_ALIASES, reset_skill_alias_cache


class Command(BaseCommand):
    help = "Dong bo danh muc ky nang mac dinh vao database."

    def handle(self, *args, **options):
        skill_count = 0
        alias_count = 0
        for skill_name, aliases in DEFAULT_SKILL_ALIASES.items():
            skill, skill_created = Skill.objects.get_or_create(name=skill_name)
            if skill_created:
                skill_count += 1
            for alias in aliases:
                if alias.casefold() == skill_name.casefold():
                    continue
                _, alias_created = SkillAlias.objects.get_or_create(skill=skill, alias=alias)
                if alias_created:
                    alias_count += 1

        reset_skill_alias_cache()
        self.stdout.write(
            self.style.SUCCESS(
                f"Da dong bo {skill_count} skill moi va {alias_count} alias moi."
            )
        )
