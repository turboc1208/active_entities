import appdaemon.appapi as appapi
import datetime
#################################
#  active_entities 
#
#  Author : Chip Cox
#  Date : 19NOV2017
#
#  Release History
#  CC     19Nov2017      V0.1     Initial Release
#
#  Description:
#    This application populates a HA group with active entities or entities that are in an on state
#
#  Setup
#  HomeAssistant
#    Create a group in Home Assistant and put one bogus entry in it as a place holder.
#  group.yaml
#  active_entities:
#    view: yes
#    entities:
#      - light.bogus
#
#  Appdaemon.YAML
#  active_entities:
#    class: active_entities
#    module: active_entities
#    active_group: group.active_entities      # for example
#    exclusion_types: ['zwave']
#    interval: 120
#    on_demand: input_boolean.demand_active_update  # for example
#    off_states: ['off', 0, 'closed']
#
#  active_group - Required - group created in groups.yaml file to hold activeed entities
#  exclusion_types: - Optional - default ['group','zone'] - type entities not to include in view.  
#  interval: Optional - default 120 seconds - seconds between updates
#  on_demand: Optional - no default - real input_boolean that can be toggled to force an update. 
#                                     I recommend not putting this entity into the active_group. 
#  off_states: Optional but suggested - states that are equivalent to "off".  Most devices have 
#                                     an "off" like state.  Where some devices use "on" other values
#                                     as in the case of a dimmer to indicate they are on.  This 
#                                     allows us to use "away" to indicate off, or "closed" for example.
#                                     because lights use numbers to indicate how bright they are, and 
#                                     fans use high/med/low, to indicate on states, checking for off
#                                     is easier than including all possible on values.
#
#################################             
class active_entities(appapi.AppDaemon):

  def initialize(self):
    # self.LOGLEVEL="DEBUG"
    if "active_group" in self.args:
      self.active_group=self.args["active_group"]
    else:
      self.log("An active_group must be setup in Home Assistant with at least one entity.  The entity can be bogus  ( light.bogus ) for example")
      exit(0)

    self.log("Orphan Group set to {}".format(self.active_group))

    if "off_states" in self.args:
      self.off_states=list(set(["off"] + self.args["off_states"]))
      self.log("Off states set to {}".format(self.off_states))
    else:
      self.off_states=["off"]

    if "exclusion_types" in self.args:
      self.exclusion_types=list(set(["group","zone","persistent_notification"]+self.args["exclusion_types"]))
    else:
      self.log("No exclusion group specified, excluding 'group' and 'zone'  entities by default")
      self.exclusion_types=["group","zone","persistent_notification"]

    if "interval" in self.args:
      interval=self.args["interval"]
    else:
      self.log("setting default interval")
      interval=60*5

    self.log("interval set to {} seconds".format(interval))

    if "on_demand" in self.args:
      self.demand_entity=self.args["on_demand"]
      self.turn_off(self.demand_entity)
      self.log("On Demand entity set to {}".format(self.demand_entity))
    else:
      self.demand_entity=None
      self.log("No self.demand_entity set")

    self.log("Exclusion types set to {}".format(self.exclusion_types))
    
    self.listen_event(self.HARestart,"HOMEASSISTANT_START")
    self.log("Event Listen event activated")
    self.run_every(self.timer_callback,self.datetime(), interval)
    self.log("Timer event registered for every {} seconds".format(interval))
    if not self.demand_entity==None :
      self.listen_state(self.demand_callback,self.demand_entity,new="on")
      self.log("Listening for {} to be turned on".format(self.demand_entity))

  #######
  #
  #  Timer Callback
  #
  #######

  def timer_callback(self,kwargs):
    self.log("Timer event fired")
    self.process_groups(self.active_group,self.exclusion_types)

  #######
  #
  # HA Restart Event Callback
  #
  #######

  def HARestart(self,event_name,dta,kwargs):
    self.log("HA Restarted creating active group membership")
    self.process_groups(self.active_group,self.exclusion_types)

  ######
  #
  # On demand listen_state callback
  #
  ######

  def demand_callback(self,entity,state,old,new,kwargs):
    self.log("on Demand callback fired")
    if new=="on":
      self.process_groups(self.active_group,self.exclusion_types)
      self.turn_off(entity)

  ######
  #
  # Process Groups - main work done here.
  #
  ######
  def process_groups(self,ogroup,etype_list):
    # first lets clear out the group.  Doing this up here, gives HA time to process the update.  We will put the new values in at the bottom
    self.set_state(ogroup,attributes={"entity_id":[]})
    # get a dictionary of all the groups in HA so we can build a list of everything that is already in a group
    allentities=self.get_state()
    group_members=[]
    if not self.demand_entity==None:
      group_members.append(self.demand_entity)

    for g in allentities:
      etyp,ename=self.split_entity(g)
      if not etyp in self.exclusion_types: 
        if self.normalize_states(g,allentities[g]["state"])=="on": 
          group_members.append(g)

    # set membership of active group
    self.set_state(ogroup,attributes={"entity_id": group_members})

  def normalize_states(self,entity,state):
    new_state=state
    etyp,ename=self.split_entity(entity)
    if state=="on":
      new_state=state
    elif state in self.off_states:
      new_state="off"
    else:
      new_state="on"
    return new_state
