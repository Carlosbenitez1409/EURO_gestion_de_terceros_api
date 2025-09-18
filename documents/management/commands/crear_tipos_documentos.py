from django.core.management.base import BaseCommand
from documents.models import TipoDocumento


class Command(BaseCommand):
    help = 'Crea tipos de documentos básicos para el sistema'

    def handle(self, *args, **options):
        tipos_documentos = [
            # Documentos para Persona Natural
            {
                'nombre': 'Documento de Identidad',
                'descripcion': 'Cédula de ciudadanía, cédula de extranjería o pasaporte',
                'es_obligatorio': True,
                'orden': 1
            },
            {
                'nombre': 'RUT',
                'descripcion': 'Registro Único Tributario',
                'es_obligatorio': True,
                'orden': 2
            },
            {
                'nombre': 'Certificación Comercial',
                'descripcion': 'Certificación comercial o de actividad económica',
                'es_obligatorio': True,
                'orden': 3
            },
            {
                'nombre': 'Certificación Bancaria',
                'descripcion': 'Certificación bancaria de la cuenta principal',
                'es_obligatorio': True,
                'orden': 4
            },
            
            # Documentos adicionales para Persona Jurídica
            {
                'nombre': 'Documento Representante Legal',
                'descripcion': 'Documento de identidad del representante legal',
                'es_obligatorio': True,
                'orden': 5
            },
            {
                'nombre': 'Certificado de Existencia',
                'descripcion': 'Certificado de existencia y representación legal',
                'es_obligatorio': True,
                'orden': 6
            },
            {
                'nombre': 'Composición Accionaria',
                'descripcion': 'Certificado de composición accionaria',
                'es_obligatorio': True,
                'orden': 7
            },
            {
                'nombre': 'Estados Financieros',
                'descripcion': 'Estados financieros del último período',
                'es_obligatorio': True,
                'orden': 8
            },
            {
                'nombre': 'Declaración de Renta',
                'descripcion': 'Declaración de renta del último año gravable',
                'es_obligatorio': True,
                'orden': 9
            },
            
            # Documento adicional para Persona Pública
            {
                'nombre': 'Resolución de Creación',
                'descripcion': 'Resolución o acto administrativo de creación de la entidad',
                'es_obligatorio': True,
                'orden': 10
            },
            
            # Documentos opcionales
            {
                'nombre': 'Poder Especial',
                'descripcion': 'Poder especial para terceros que actúan en representación',
                'es_obligatorio': False,
                'orden': 11
            },
            {
                'nombre': 'Autorización Terceros',
                'descripcion': 'Autorización para manejo por terceros',
                'es_obligatorio': False,
                'orden': 12
            }
        ]

        created_count = 0
        for tipo_data in tipos_documentos:
            tipo, created = TipoDocumento.objects.get_or_create(
                nombre=tipo_data['nombre'],
                defaults=tipo_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Creado: {tipo.nombre}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'- Ya existe: {tipo.nombre}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n¡Proceso completado! {created_count} tipos de documentos creados.'
            )
        )
