import json
import csv
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from japb_api.currencies.models import CurrencyConversionHistorial


class Command(BaseCommand):
    help = 'Dump CurrencyConversionHistorial data to JSON or CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'csv'],
            default='json',
            help='Output format: json or csv (default: json)'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (default: stdout)'
        )
        parser.add_argument(
            '--source',
            type=str,
            choices=['paralelo', 'bcv'],
            help='Filter by source (paralelo or bcv)'
        )
        parser.add_argument(
            '--currency-from',
            type=str,
            help='Filter by currency_from name (e.g., VES)'
        )
        parser.add_argument(
            '--currency-to',
            type=str,
            help='Filter by currency_to name (e.g., USD)'
        )

    def handle(self, *args, **options):
        format_type = options['format']
        output_file = options['output']
        source_filter = options.get('source')
        currency_from_filter = options.get('currency_from')
        currency_to_filter = options.get('currency_to')

        # Build queryset
        queryset = CurrencyConversionHistorial.objects.all().select_related(
            'currency_from', 'currency_to', 'user'
        ).order_by('-date')

        # Apply filters
        if source_filter:
            queryset = queryset.filter(source=source_filter)
        
        if currency_from_filter:
            queryset = queryset.filter(currency_from__name=currency_from_filter)
        
        if currency_to_filter:
            queryset = queryset.filter(currency_to__name=currency_to_filter)

        # Get data
        data = list(queryset.values(
            'id',
            'currency_from__name',
            'currency_to__name',
            'source',
            'rate',
            'date',
            'user__id',
            'user__email'
        ))

        # Format data for output
        formatted_data = []
        for item in data:
            formatted_item = {
                'id': item['id'],
                'currency_from': item['currency_from__name'],
                'currency_to': item['currency_to__name'],
                'source': item['source'],
                'rate': item['rate'],
                'date': item['date'].isoformat() if item['date'] else None,
                'user_id': item['user__id'],
                'user_email': item['user__email']
            }
            formatted_data.append(formatted_item)

        # Output data
        if format_type == 'json':
            output = json.dumps(formatted_data, indent=2, cls=DjangoJSONEncoder)
        else:  # csv
            if not formatted_data:
                output = ''
            else:
                import io
                output_buffer = io.StringIO()
                fieldnames = ['id', 'currency_from', 'currency_to', 'source', 'rate', 'date', 'user_id', 'user_email']
                writer = csv.DictWriter(output_buffer, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(formatted_data)
                output = output_buffer.getvalue()

        # Write to file or stdout
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully dumped {len(formatted_data)} records to {output_file}'
                )
            )
        else:
            self.stdout.write(output)
            if formatted_data:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nDumped {len(formatted_data)} records'
                    )
                )

