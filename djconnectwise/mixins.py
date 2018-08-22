
class SlaGoalsMixin(object):
    """
    TODO write something here
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
