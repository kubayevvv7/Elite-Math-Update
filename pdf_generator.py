import logging
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from io import BytesIO

logger = logging.getLogger(__name__)

def create_homework_results_pdf(homework_name, homework_id, results):
    """
    PDF file yaratadi homework natijalari uchun
    
    Args:
        homework_name: Uyga vazifa nomi
        homework_id: Uyga vazifa ID
        results: [(student_name, username, tg_id, correct, incorrect, date), ...] format
    
    Returns:
        PDF file bytes
    """
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
            title=f"Uyga vazifa natijalari - {homework_name}"
        )
        
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=20,
            alignment=1  # Center
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#2e5c8a'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        story = []
        
        # Title
        title = Paragraph(f"📊 UYGA VAZIFA NATIJALARI", title_style)
        story.append(title)
        
        # Homework info
        info_data = [
            ["Uyga vazifa nomi:", homework_name],
            ["ID raqami:", str(homework_id)],
            ["Yaratilgan sana:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f0f7')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Results heading
        results_heading = Paragraph(f"Topshirilgan javoblar: {len(results)} ta o'quvchi", heading_style)
        story.append(results_heading)
        
        # Results table
        if results:
            # Group results by student
            user_stats = {}
            for r in results:
                student_name, username, tg_id, correct, incorrect, date = r
                key = (student_name, username, tg_id)
                if key not in user_stats:
                    user_stats[key] = {"correct": 0, "incorrect": 0, "attempts": 0, "dates": []}
                user_stats[key]["correct"] += correct
                user_stats[key]["incorrect"] += incorrect
                user_stats[key]["attempts"] += 1
                user_stats[key]["dates"].append(date)
            
            # Create table data
            table_data = [
                ["#", "O'quvchi", "Foydalanuvchi", "To'g'ri", "Xato", "Foiz %", "Topshirilgan", "Oxirgi vaqti"],
            ]
            
            for idx, ((student_name, username, tg_id), stats) in enumerate(
                sorted(user_stats.items(), key=lambda x: x[1]["correct"], reverse=True), 1
            ):
                user_display = f"@{username}" if username else f"tg:{tg_id}"
                total = stats["correct"] + stats["incorrect"]
                percentage = (stats["correct"] / total * 100) if total > 0 else 0
                
                table_data.append([
                    str(idx),
                    student_name[:20],
                    user_display[:15],
                    str(stats["correct"]),
                    str(stats["incorrect"]),
                    f"{percentage:.1f}%",
                    str(stats["attempts"]),
                    stats["dates"][0][:10]
                ])
            
            # Create results table
            results_table = Table(table_data, colWidths=[0.4*inch, 1.2*inch, 1.2*inch, 0.6*inch, 0.6*inch, 0.7*inch, 0.7*inch, 1*inch])
            results_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c8a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f5f9')]),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'LEFT'),
            ]))
            
            story.append(results_table)
            
            # Summary statistics
            story.append(Spacer(1, 0.2*inch))
            
            total_students = len(user_stats)
            total_correct = sum(stats["correct"] for stats in user_stats.values())
            total_incorrect = sum(stats["incorrect"] for stats in user_stats.values())
            total_attempts = sum(stats["attempts"] for stats in user_stats.values())
            avg_percentage = (total_correct / (total_correct + total_incorrect) * 100) if (total_correct + total_incorrect) > 0 else 0
            
            summary_data = [
                ["Jami o'quvchi:", str(total_students)],
                ["Jami to'g'ri javob:", str(total_correct)],
                ["Jami xato javob:", str(total_incorrect)],
                ["O'rtacha foiz:", f"{avg_percentage:.1f}%"],
                ["Jami topshirilgan:", str(total_attempts)],
            ]
            
            summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f0f7')),
                ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#d0e0f0')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))
            
            story.append(summary_table)
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    except Exception as e:
        logger.exception(f"PDF generation error: {e}")
        return None


def create_student_homework_results_pdf(student_name, homework_results):
    """
    O'quvchining uyga vazifa natijalari uchun PDF yaratadi
    
    Args:
        student_name: O'quvchi ismi
        homework_results: [(homework_name, homework_id, correct, incorrect, date), ...]
    
    Returns:
        PDF file bytes
    """
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
            title=f"{student_name} - Uyga vazifa natijalari"
        )
        
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=20,
            alignment=1
        )
        
        story = []
        
        # Title
        title = Paragraph(f"📊 UYGA VAZIFA NATIJALARI", title_style)
        story.append(title)
        
        # Student info
        info_data = [
            ["O'quvchi ismi:", student_name],
            ["Hisobot sana:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f0f7')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Results table
        if homework_results:
            table_data = [
                ["Uyga vazifa", "ID", "To'g'ri", "Xato", "Foiz %", "Vaqti"],
            ]
            
            for homework_name, homework_id, correct, incorrect, date in homework_results:
                total = correct + incorrect
                percentage = (correct / total * 100) if total > 0 else 0
                
                table_data.append([
                    homework_name[:20],
                    str(homework_id),
                    str(correct),
                    str(incorrect),
                    f"{percentage:.1f}%",
                    date[:10]
                ])
            
            results_table = Table(table_data, colWidths=[2*inch, 1*inch, 0.8*inch, 0.8*inch, 1*inch, 1*inch])
            results_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c8a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f5f9')]),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ]))
            
            story.append(results_table)
            
            # Summary
            story.append(Spacer(1, 0.2*inch))
            total_correct = sum(c for _, _, c, _, _ in homework_results)
            total_incorrect = sum(inc for _, _, _, inc, _ in homework_results)
            avg_percentage = (total_correct / (total_correct + total_incorrect) * 100) if (total_correct + total_incorrect) > 0 else 0
            
            summary_data = [
                ["Jami to'g'ri javob:", str(total_correct)],
                ["Jami xato javob:", str(total_incorrect)],
                ["O'rtacha foiz:", f"{avg_percentage:.1f}%"],
            ]
            
            summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f0f7')),
                ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#d0e0f0')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))
            
            story.append(summary_table)
        
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    except Exception as e:
        logger.exception(f"PDF generation error: {e}")
        return None
