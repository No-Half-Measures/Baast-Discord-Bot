from django.db import migrations, models

class Migration(migrations.Migration):
    
    def update_attendance_guild_field(apps, schema_editor):
        Attendance = apps.get_model('app', 'Attendance')
        Events = apps.get_model('app', 'Events')
        
        for a in Attendance.objects.all():
            evt = a.id
            a.guild = evt.gid
            a.save()
            
    def migrate_old_attendance_data(apps, schema_editor):
        Attendance = apps.get_model('app', 'Attendance')
        
        for a in Attendance.objects.all():
            attending = a.attending
            declined = a.declined
            tentative = a.tentative
            
            for att in attending:
                a.option_1.append(att)
            
            for dec in declined:
                a.option_2.append(dec)
                
            for tent in tentative:
                a.option_3.append(tent)
                
            a.save()

    dependencies = [
        ('app', '0009_events_links_option_presets_templates_and_more'),
    ]

    operations = [
        migrations.RunPython(update_attendance_guild_field),
        migrations.RunPython(migrate_old_attendance_data),
    ]
