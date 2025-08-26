# -*- coding:utf-8 -*-

from collections import defaultdict
from datetime import timedelta
from pytz import utc
from odoo import models
from odoo.tools import float_utils

# Use sixteenth-of-a-day granularity when converting hours -> day fractions
ROUNDING_FACTOR = 16


class ResourceMixin(models.AbstractModel):
    """
        Extend `resource.mixin` with a helper to compute worked time.
        Calculates worked **days** and **hours** between two datetimes using the
        employee's (resource's) calendar, optionally excluding leaves.
    """
    _inherit = "resource.mixin"

    def _get_work_days_data(self, from_datetime, to_datetime,
                            compute_leaves=True, calendar=None,
                            domain=None):
        """
            Compute worked time between two datetimes.

            Parameters
            ----------
            from_datetime : datetime
                Period start (naive datetimes are treated as UTC).
            to_datetime : datetime
                Period end (naive datetimes are treated as UTC).
            compute_leaves : bool, optional
                If True, exclude leaves using `domain`; otherwise use pure attendances.
            calendar : resource.calendar | None, optional
                Calendar to use; defaults to the record's resource calendar.
            domain : list | None, optional
                Domain to identify leaves (defaults to [('time_type', '=', 'leave')] upstream).

            Returns
            -------
            dict
                {'days': <float>, 'hours': <float>} where:
                  - 'hours' is the total worked hours in the window,
                  - 'days' is hours expressed as day fractions, rounded to 1/16th.
        """
        resource = self.resource_id
        calendar = calendar or self.resource_calendar_id

        # Normalize naive datetimes to explicit UTC
        if not from_datetime.tzinfo:
            from_datetime = from_datetime.replace(tzinfo=utc)
        if not to_datetime.tzinfo:
            to_datetime = to_datetime.replace(tzinfo=utc)

        # Build per-day total attendances over a slightly wider window
        from_full = from_datetime - timedelta(days=1)
        to_full = to_datetime + timedelta(days=1)
        intervals = calendar._attendance_intervals_batch(from_full, to_full, resource)
        day_total = defaultdict(float)
        for start, stop, meta in intervals[resource.id]:
            day_total[start.date()] += (stop - start).total_seconds() / 3600

        # Build per-day actual worked hours (attendance or work intervals minus leaves)
        if compute_leaves:
            intervals = calendar._work_intervals_batch(from_datetime, to_datetime, resource, domain)
        else:
            intervals = calendar._attendance_intervals_batch(from_datetime, to_datetime, resource)
        day_hours = defaultdict(float)
        for start, stop, meta in intervals[resource.id]:
            day_hours[start.date()] += (stop - start).total_seconds() / 3600

        # Convert hours to day fractions (rounded to 1/16th of a day)
        days = sum(
            float_utils.round(ROUNDING_FACTOR * day_hours[day] / day_total[day]) / ROUNDING_FACTOR
            for day in day_hours
        )
        return {
            'days': days,
            'hours': sum(day_hours.values()),
        }
