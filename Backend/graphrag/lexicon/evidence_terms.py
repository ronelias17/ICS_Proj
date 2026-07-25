from __future__ import annotations

from graphrag.lexicon.question_terms import QUESTION_TERMS


EVIDENCE_TERMS = {
    "course_curriculum": ("תכנית הלימודים", "תוכנית הלימודים", "לימודי ליבה", "קורסי חובה"),
    "required_course_evidence": ("קורס", "תכנית הלימודים", "תוכנית הלימודים", "לימודי ליבה", 'נ"ז'),
    "required_course_core": ("לימודי ליבה",),
    "required_course_elective": ("קורסי בחירה",),
    "admission_chunk_noise": ("תנאי קבלה", "קבלה לתואר", "נקודות זכות מהאוניברסיטה הפתוחה"),
    "admission_title_marker": ("תנאי קבלה לתואר",),
    "scholarship_text": ("מלג",),
    "scholarship_criteria_text": ("פסיכומטרי", "בגרות", "שכר לימוד בסיסי מלא", "112", "670", "650", "300%", "400%"),
    "document_evidence": ("מסמכים", "מכתבי המלצה", "מכתב המלצה", "טופס", "קורות חיים", "אישור", "להגיש", "להעביר"),
    "document_context": ("תנאי הרשמה", "דרישות", "מועד אחרון להרשמה"),
    "sports_text": ("ספורט", "נבחרות", "כדורסל", "כדורעף", 'אס"א', "אסא"),
    "admission_specialization_noise": ("מסלולי התמחות", "פתיחת התמחות", "קבלה להתמחות"),
    "payment_noise": ("שכר לימוד", "דמי הרשמה", "תשלום", "מקדמה"),
    "degree_structure_payment_noise": ("שכר לימוד", "במזומן", "תשלום"),
    "parking_policy": ("מנוי לחניה", "מנוי חניה", "מנוי בחניה", "מפעיל החניון", "IPI"),
    "parking_chunk": QUESTION_TERMS["parking"] + ("מנוי חניה", "חנייה שמורה"),
    "parking_location_text": ("נמצא", "נמצאת", "מיקום", "צדו", "הגעה", "קמפוס"),
    "parking_location_context": ("נמצא", "נמצאת", "צדו", "הגעה"),
    "parking_entity_text": ("חניון",),
    "parking_price_text": ("מחירים", "מסלולים", "מנוי", "₪"),
    "housing_price_table": ("דירת סטודיו", "שם/סוג דירה", "מחיר לחודש לסטודנט", "חדר בדירה"),
    "total_credits_text": ("נקודות זכות", 'נ"ז'),
    "general_criteria_title": ("קריטריונים כללים",),
}
