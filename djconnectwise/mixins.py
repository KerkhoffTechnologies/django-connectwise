
class SlaGoalsMixin(object):
    """
    Returns the fields relevant to SLA goals for models with SLA information
    """

    def get_stage_hours(self, stage):
        if stage == 'respond':
            return self.respond_hours
        elif stage == 'plan':
            return self.plan_within
        elif stage == 'resolve':
            return self.resolution_hours
        elif stage == 'waiting':
            return 0
        else:
            return None
