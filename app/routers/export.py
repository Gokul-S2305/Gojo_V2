from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.database import get_session
from app.models import User, Trip, TripUserLink, Expense, ItineraryItem, Document
from app.auth_utils import get_current_user
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
import tempfile
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _cleanup_temp_file(path: str):
    """Background task: delete temp file after response is sent."""
    try:
        os.unlink(path)
    except Exception as e:
        logger.warning(f"Could not delete temp file {path}: {e}")


@router.get("/trip/{trip_id}/export/pdf")
async def export_trip_pdf(
    trip_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    trip_statement = select(Trip).where(Trip.id == trip_id)
    trip_result = await session.execute(trip_statement)
    trip = trip_result.scalar_one_or_none()

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    link_statement = select(TripUserLink).where(
        TripUserLink.trip_id == trip_id,
        TripUserLink.user_id == user.id
    )
    link_result = await session.execute(link_statement)
    if not link_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Trip not found")

    # Get members via JOIN
    members_statement = (
        select(User, TripUserLink)
        .join(TripUserLink, User.id == TripUserLink.user_id)
        .where(TripUserLink.trip_id == trip_id)
    )
    members_result = await session.execute(members_statement)
    members_data = members_result.all()

    # Get expenses with user info via JOIN
    expenses_statement = (
        select(Expense, User)
        .join(User, Expense.user_id == User.id)
        .where(Expense.trip_id == trip_id)
        .order_by(Expense.created_at.desc())
    )
    expenses_result = await session.execute(expenses_statement)
    expenses_data = expenses_result.all()
    total_expenses = sum(e.amount for e, _ in expenses_data)

    # Get itinerary
    itinerary_statement = (
        select(ItineraryItem)
        .where(ItineraryItem.trip_id == trip_id)
        .order_by(ItineraryItem.day_number, ItineraryItem.order_index, ItineraryItem.time)
    )
    itinerary_result = await session.execute(itinerary_statement)
    itinerary_items = itinerary_result.scalars().all()

    # Get documents/tickets
    docs_statement = (
        select(Document)
        .where(Document.trip_id == trip_id)
        .order_by(Document.created_at.desc())
    )
    docs_result = await session.execute(docs_statement)
    docs_items = docs_result.scalars().all()

    # Build PDF
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story = []

    styles = getSampleStyleSheet()
    brand_blue = colors.HexColor('#4F46E5')
    text_slate = colors.HexColor('#0F172A')

    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'],
        fontSize=22, textColor=brand_blue,
        spaceAfter=15, alignment=TA_CENTER, fontName='Helvetica-Bold'
    )
    heading_style = ParagraphStyle(
        'CustomHeading', parent=styles['Heading2'],
        fontSize=13, textColor=brand_blue,
        spaceAfter=8, spaceBefore=14, fontName='Helvetica-Bold'
    )

    story.append(Paragraph(f"{trip.name} · Trip Summary", title_style))
    story.append(Paragraph("Gojo Trip Planner", ParagraphStyle('Sub', parent=styles['Normal'], alignment=TA_CENTER, textColor=colors.grey)))
    story.append(Spacer(1, 0.2 * inch))

    # Trip Information
    story.append(Paragraph("Trip Overview", heading_style))
    duration = (trip.end_date - trip.start_date).days + 1
    trip_data = [
        ['Destination:', trip.destination, 'Duration:', f"{duration} days"],
        ['Start Point:', trip.start_location or 'N/A', 'Join Code:', trip.join_code],
        ['Start Date:', str(trip.start_date), 'End Date:', str(trip.end_date)],
    ]
    trip_table = Table(trip_data, colWidths=[1.3 * inch, 2.3 * inch, 1.2 * inch, 2.2 * inch])
    trip_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#F8FAFC')),
        ('TEXTCOLOR', (0, 0), (-1, -1), text_slate),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    story.append(trip_table)

    # Members
    story.append(Paragraph(f"Travelers ({len(members_data)})", heading_style))
    members_data_table = [['Name', 'Email', 'Role']]
    for member, link in members_data:
        members_data_table.append([
            member.full_name or 'N/A',
            member.email,
            link.role.capitalize()
        ])
    members_table = Table(members_data_table, colWidths=[2.2 * inch, 3.3 * inch, 1.5 * inch])
    members_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), brand_blue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]))
    story.append(members_table)

    # Itinerary
    if itinerary_items:
        story.append(Paragraph("Itinerary", heading_style))
        itin_data = [['Day', 'Time', 'Activity', 'Location']]
        for item in itinerary_items:
            itin_data.append([
                f"Day {item.day_number}",
                item.time or '-',
                item.activity,
                item.location or '-',
            ])
        itin_table = Table(itin_data, colWidths=[0.8 * inch, 0.9 * inch, 3.2 * inch, 2.1 * inch])
        itin_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0D9488')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ]))
        story.append(itin_table)

    # Tickets and Bookings
    if docs_items:
        story.append(Paragraph(f"Bookings & Tickets ({len(docs_items)})", heading_style))
        doc_rows = [['Type', 'Title', 'Vendor', 'Booking Ref', 'Dates / Route']]
        for doc_item in docs_items:
            route_str = ""
            if doc_item.from_location or doc_item.to_location:
                route_str = f"{doc_item.from_location or ''} → {doc_item.to_location or ''}"
            elif doc_item.date_from:
                route_str = doc_item.date_from
            doc_rows.append([
                doc_item.doc_type.capitalize(),
                doc_item.title,
                doc_item.vendor or '-',
                doc_item.booking_ref or '-',
                route_str or '-',
            ])
        doc_table = Table(doc_rows, colWidths=[1.0 * inch, 2.0 * inch, 1.3 * inch, 1.3 * inch, 1.4 * inch])
        doc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#475569')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ]))
        story.append(doc_table)

    # Expenses
    story.append(Paragraph(f"Expenses (Total: ₹{total_expenses:,.2f})", heading_style))
    if expenses_data:
        expense_rows = [['Purpose', 'Category', 'Amount', 'Paid By', 'Date']]
        for expense, exp_user in expenses_data:
            expense_rows.append([
                expense.purpose,
                expense.category,
                f"₹{expense.amount:,.2f}",
                exp_user.full_name or exp_user.email,
                expense.created_at.strftime('%d %b %Y') if expense.created_at else '-',
            ])
        expense_rows.append(['Total Spent', '', f"₹{total_expenses:,.2f}", '', ''])

        expense_table = Table(expense_rows, colWidths=[2.2 * inch, 1.2 * inch, 1.3 * inch, 1.3 * inch, 1.0 * inch])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), brand_blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#EEF2FF')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ]))
        story.append(expense_table)

    story.append(Spacer(1, 0.3 * inch))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    story.append(Paragraph(f"Exported from Gojo · {user.full_name or user.email}", footer_style))

    doc.build(story)
    pdf_buffer.seek(0)

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    temp_file.write(pdf_buffer.read())
    temp_file.close()

    background_tasks.add_task(_cleanup_temp_file, temp_file.name)

    safe_name = "".join(c for c in trip.name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    filename = f"{safe_name}_Gojo_Report.pdf"
    return FileResponse(temp_file.name, media_type='application/pdf', filename=filename)
