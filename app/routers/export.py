from fastapi import APIRouter, Request, Depends
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink, Expense
from app.auth_utils import get_current_user
from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
import tempfile

router = APIRouter()

@router.get("/trip/{trip_id}/export/pdf")
async def export_trip_pdf(
    trip_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    
    # Get trip
    trip_statement = select(Trip).where(Trip.id == trip_id)
    trip_result = await session.execute(trip_statement)
    trip = trip_result.scalar_one_or_none()
    
    if not trip:
        return RedirectResponse("/dashboard", status_code=302)
    
    # Check if user is member
    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        return RedirectResponse("/dashboard", status_code=302)
    
    # Get members
    members_statement = select(User).join(TripUserLink).where(TripUserLink.trip_id == trip_id)
    members_result = await session.execute(members_statement)
    members = members_result.scalars().all()
    
    # Get expenses
    expenses_statement = select(Expense).where(Expense.trip_id == trip_id).order_by(Expense.created_at.desc())
    expenses_result = await session.execute(expenses_statement)
    expenses = expenses_result.scalars().all()
    
    # Load user relationship for expenses
    for expense in expenses:
        await session.refresh(expense, ["user"])
    
    # Calculate total
    total_expenses = sum(expense.amount for expense in expenses)
    
    # Generate PDF
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#6C63FF'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#6C63FF'),
        spaceAfter=12,
        spaceBefore=20
    )
    
    # Title
    story.append(Paragraph(f"🗺️ {trip.name}", title_style))
    story.append(Paragraph(f"Trip Summary Report", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Trip Details
    story.append(Paragraph("Trip Information", heading_style))
    trip_data = [
        ['Destination:', trip.destination],
        ['Start Date:', str(trip.start_date)],
        ['End Date:', str(trip.end_date)],
        ['Duration:', f"{(trip.end_date - trip.start_date).days + 1} days"],
        ['Join Code:', trip.join_code]
    ]
    trip_table = Table(trip_data, colWidths=[2*inch, 4*inch])
    trip_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F0F0F0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    story.append(trip_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Members
    story.append(Paragraph("Trip Members", heading_style))
    members_data = [['Name', 'Email']]
    for member in members:
        members_data.append([member.full_name or 'N/A', member.email])
    
    members_table = Table(members_data, colWidths=[2.5*inch, 3.5*inch])
    members_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6C63FF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    story.append(members_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Budget Summary
    story.append(Paragraph("Budget Summary", heading_style))
    if expenses:
        expense_data = [['Purpose', 'Amount (₹)', 'Added By', 'Date']]
        for expense in expenses:
            expense_data.append([
                expense.purpose,
                f"₹{expense.amount:.2f}",
                expense.user.full_name or expense.user.email,
                expense.created_at.strftime('%b %d, %Y') if expense.created_at else 'N/A'
            ])
        
        # Add total row
        expense_data.append(['', 'Total:', f"₹{total_expenses:.2f}", ''])
        
        expense_table = Table(expense_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6C63FF')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFE5B4')),
            ('FONTNAME', (1, -1), (2, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        story.append(expense_table)
    else:
        story.append(Paragraph("No expenses recorded yet.", styles['Normal']))
    
    story.append(Spacer(1, 0.5*inch))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    story.append(Paragraph("Generated by Gojo Trip Planner", footer_style))
    story.append(Paragraph(f"Exported by: {user.full_name or user.email}", footer_style))
    
    # Build PDF
    doc.build(story)
    pdf_buffer.seek(0)
    
    # Save to temp file and return
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    temp_file.write(pdf_buffer.read())
    temp_file.close()
    
    filename = f"{trip.name.replace(' ', '_')}_Summary.pdf"
    
    return FileResponse(
        temp_file.name,
        media_type='application/pdf',
        filename=filename
    )
