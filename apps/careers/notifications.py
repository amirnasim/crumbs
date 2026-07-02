"""Career application submission logging."""

import logging

logger = logging.getLogger(__name__)


def log_new_career_application(application) -> None:
    logger.info(
        "New career application #%s from %s (%s) for %s",
        application.pk,
        application.full_name,
        application.phone,
        application.get_desired_position_display(),
    )
