from django.db import models

# Create your models here.
class PickerModel(models.Model):
    id = models.BigIntegerField(primary_key=True, serialize=True)
    