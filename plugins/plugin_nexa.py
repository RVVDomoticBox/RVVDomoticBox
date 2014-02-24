# -*- coding: utf-8 -*-

#---------------------------------------------------------------
# Plugin importable permettant à la centrale de gérer le 
# protocole Nexa. C'est un plugin de type protocol. D'une part, 
# elle comporte le driver et d'autre part les nouveaux 
# périphériques qu'elle apporte.
#---------------------------------------------------------------

# TODO: réflechir à cette histoire de core_classes
from core_classes import * 

PLUGIN_TYPE = 'protocol'
""" Module variable allowing the Kernel to determine the type
of the plugin and to instantiate it accordingly. 

"""

class Driver():
	""" Main class of a protocol plugin.
	
	"""

	#---------------------------------------------------------------
	# Interface avec le kernel 
	#---------------------------------------------------------------

	def __init__(self, kernel):
		self.kernel = kernel
		
		# Jusqu'à ce qu'on l'ait configuré, le driver n'a pas encore de modem
		self.modem = None

		# On définit la structure de messages radio propre au protocole nexa 
		self.message_structure = 4*32*[((200,300),(2000,2500))]
		
		{
								'baselength' : 250,
								'symbols' : {
										'start' : [1,10],
										'one' : [1,5,1,1],
										'zero' : [1,1,1,5],
										'end' : [1,30]
										},
								'structure' : ['start'] + 32*[('one','zero')] + ['end']
								}

		# Liste des périphériques connectés gérés par ce driver
		self.devices = []
		
		# Paramètres à fournir pour configurer le driver
		self.settings = {'modem' : ('Modem', None)}
		
		# Liste des périphériques potentiellement gérables par ce driver
		self.handled_devices = [NexaSwitch, NexaVirtualRemote]
		
		# Le driver ne propose à l'extérieur d'instantier un périphérique
		# seulement si cela a un sens. Ici, un NexaSwitch ne sera instantié
		# que si on en détecte un, automatiquement.
		self.instantiable_devices = [NexaVirtualRemote]

		# Nécessaire pour l'interface
		self.name = "Nexa"
			
	def get_set_arguments(self):
		""" Returns the arguments needed to set the driver.	"""
		return self.settings
	
	def set(self, args):
		""" Sets the driver. Returns True if the setting was a success. 
		Otherwise, it returns a tuple containing the setting which caused 
		the issue.
		
		Keyword arguments:
		settings -- the dictionary of settings used to set the driver. Its 
		format is determined by the function get_set_arguments.
		
		"""
		
		# On vérifie que les arguments donnés sont valides
		retour = True
		if args['modem'].get_modem_type() == 'radio_433': 
			self.modem = args['modem']
			# On spécifie au modem la structure de message qu'on attend au modem 
			# pour qu'il nous transmette ce qui est nous est adressé
			self.modem.attach({
							'structure' : 4*32*[[(150,350),(1000,1500)]],
							'i' : 0,
							'length' : 4*32,
							'method' : self.decode_sequence})
		else:
			retour = ('modem', "Le modem specifié n'est pas du bon type")
		return retour

	def get_instantiable_devices(self):
		""" Returns a list of the devices instantiable by the user
		of the driver. 
		The list of user-instantiable devices is included in the 
		list of the driver-handled devices but not necessarily 
		equal.  
		
		"""
		# On ne fournit pas directement la classe pour que le driver reste
		# le seul à pouvoir instancier des périphériques
		return [i.device_infos for i in self.instantiable_devices]

	def add_device(self, device_id, args):
		""" Proxy method used to instantiate a new device. Returns True
		if the instantiation has succeeded, otherwise the arguments which
		caused an issue.
 		 
		"""
		retour = True
		if device_id == 0:
			new_device = NexaVirtualRemote()
			# TODO: Vérifier que les bons arguments sont fournis
			# avec une fonction générique (ce problème se pose 
			# souvent dans le programme)
			new_device.set(self, args)
			self.devices.append(new_device)
			self.kernel.devices.append(new_device)
		else:
			retour = ('device_id', "device_id out of range")
		
		return retour
	
	def get_devices(self):
		return self.devices

	#---------------------------------------------------------------
	# Interface avec le modem 
	#---------------------------------------------------------------

	# Reçoit une trame identifiée comme destinée à ce driver et
	# transmise par la couche inférieure. Cela suppose que la couche la
	# plus basse a la capacité d'identifier le protocole du message et
	# s'adresse ainsi directement à la méthode decode_sequence du
	# driver.
	# La méthode doit être spécialisée pour traiter et décoder une trame Nexa
	# Elle sera totalement rédigée quand on saura sous quelle forme le message est obtenu
	def decode_sequence(self, sequence):
		# TODO: Transformation de ce qui est reçu du modem en message de 32 bits
		# Transformation d'un tableau de bits en entiers
		#print len(sequence)
		#print sequence
		
		def is_short(duration):
			return True if (0 < duration*32 < 800) else False
		
		def is_long(duration):
			return True if (800 < duration*32 < 2000) else False
		
		for index in range(len(sequence)):
			if is_short(sequence[index]):
				sequence[index] = 'short'
			else:
				sequence[index] = 'long'
		#print sequence
		
		abort = False
		temp_list = [0,0,0,0]
		nexa_sequence = []
		for j in range(len(sequence)/4):
			for i in range(4):
				temp_list[i] = sequence.pop(0)
			
			#print temp_list
			if temp_list == ['short', 'long', 'short', 'short']:
				nexa_sequence += [1]
			elif temp_list == ['short', 'short', 'short', 'long']:
				nexa_sequence += [0]
			else:
				abort = True
		
		if not abort:
			def from_bitfield_to_int(bitfield):
				return sum([i*2**(len(bitfield)-1-idi) for idi, i in enumerate(bitfield)])
			
			house_code = from_bitfield_to_int(nexa_sequence[0:26])
			group_code = nexa_sequence[26]
			command = nexa_sequence[27]
			unit_code = from_bitfield_to_int(nexa_sequence[28:32])
			
			device_found = False
			for device in self.devices:
				if device.house_code == house_code and device.unit_code == unit_code:
					device_found = True
					# TODO: Il faudrait vérifier qu'on a bien à faire à un sensor
					device.update(command)
			if not device_found:
				new_device = NexaSwitch()
				new_device.set(self, {
									'name' : "New Nexa Switch",
									'description' : "A new Nexa Switch has been detected and added to your devices.",
									'location' : "Specify a location.",
									'house_code' : house_code,
									'group_code' : group_code,
									'unit_code' : unit_code})
				self.devices.append(new_device)
				self.kernel.devices.append(new_device)
	#---------------------------------------------------------------
	# Interface avec les devices 
	#---------------------------------------------------------------

	def send_command(self, device, command):
		error_code = True
		
		symbols = ['1' + 10*'0',
				'10000010',
				'10100000',
				'1' + 40*'0']

		bin_house_code = (26-len(bin(device.house_code)[2:]))*'0' + bin(device.house_code)[2:]
		bin_group_code = bin(device.group_code)[2:]
		bin_command = bin(command)[2:]
		bin_unit_code = (4-len(bin(device.unit_code)[2:]))*'0' + bin(device.unit_code)[2:]
	
		nexa_sequence = bin_house_code + bin_group_code + bin_command + bin_unit_code
		
		coded_sequence = [0]
		for char in nexa_sequence:
			if char == '1':
				coded_sequence += [1]
			else:
				coded_sequence += [2]
		coded_sequence += [3]
		
		call_arg = [16,250] + symbols + [coded_sequence]
		self.modem.send_sequence(call_arg)
		
		
# 		try:
# 			self.modem.send_sequence([16,250].extend(symbols) + coded_sequence)
# 		except:
# 			print "problème dans send_sequence"
# 			error_code = False
			
		return error_code

#---------------------------------------------------------------

# Interrupteur Nexa classique on/off
class NexaSwitch(Device):

	# Ce sont les attributs qui caractérisent ce type de périphérique
	device_infos = {
				'device_name' : "Nexa Switch",
				'device_brand' : "Nexa",
				'device_description' : "Interrupteur Nexa on/off",
				'arguments' : {
							'name' : ('string', 50),
							'description' : ('string', 1000),
							'location' : ('string', 100),
							'house_code' : ('integer', (0,67108863)),
							'group_code' : ('integer', (0,1)),
							'unit_code' : ('integer', (0,15))}}

	def __init__(self):
		self.name = None
		self.description = None
		self.location = None
		self.driver = None
		
		self.house_code = None
		self.group_code = None
		self.unit_code = None
		
		self.informations = []
		self.informations. append(Information("Etat de l'interrupteur",
											"Décrit l'état de l'interrupteur",
											("state", ("on", "off"))))
		self.actions = []
		self.actions.append(Action(
								"on", 
								"appuyer sur le bouton on de la télécommande", 
								self.switch_on, 
								{}))
		self.actions.append(Action(
								"off", 
								"appuyer sur le bouton off de la télécommande", 
								self.switch_off, 
								{}))
		self.actions.append(Action(
								"sync", 
								"synchroniser la télécommande", 
								self.sync, 
								{}))
		self.actions.append(Action(
								"unsync", 
								"désynchroniser la télécommande", 
								self.unsync, 
								{}))
		
	def set(self, driver, args):
		# TODO: vérifier la cohérence des arguments fournis avec ce qui a été demandé
		self.name = args['name']
		self.description = args['description']
		self.location = args['location']
		self.driver = driver
		
		self.house_code = args['house_code']
		self.group_code = args['group_code']
		self.unit_code = args['unit_code']
		
		#print self

	def switch_on(self, args):
		#print"switch_on"
		self.driver.send_command(self, 1)

	def switch_off(self, args):
		self.driver.send_command(self, 0)
	
	def sync(self, args):
		for i in range(5):
			self.switch_on({})
			time.sleep(0.1)
	
	def unsync(self, args):
		for i in range(5):
			self.switch_off({})
			time.sleep(0.1)
	
	def update(self, new_command):
		retour = True
		if new_command == 1:
			self.informations[0].update("on")
		elif new_command == 0:
			self.informations[0].update("off")
		else:
			retour = "La nouvelle commande n'était ni un 1 ni un 0."
		return retour

#---------------------------------------------------------------

# Permet de simuler une télécommande Nexa 
class NexaVirtualRemote(Device):

	# Ce sont les attributs qui caractérisent ce type de périphérique
	device_infos = {
				'device_name' : "Nexa Virtual Remote",
				'device_brand' : "Nexa",
				'device_description' : "Simulation d'une télécommande deux états Nexa",
				'arguments' : {
							'name' : ('string', 50),
							'description' : ('string', 1000),
							'location' : ('string', 100),
							'house_code' : ('integer', (0,67108863)),
							'group_code' : ('integer', (0,1)),
							'unit_code' : ('integer', (0,15))}}

	def __init__(self):
		self.name = None
		self.description = None
		self.location = None
		self.driver = None
		
		self.house_code = None
		self.group_code = None
		self.unit_code = None
		
		self.informations = []
		self.informations. append(Information("Etat de l'interrupteur",
											"Décrit l'état de l'interrupteur",
											("state", ("on", "off"))))
		
		self.actions = []
		self.actions.append(Action(
								"on", 
								"appuyer sur le bouton on de la télécommande", 
								self.switch_on, 
								{}))
		self.actions.append(Action(
								"off", 
								"appuyer sur le bouton off de la télécommande", 
								self.switch_off, 
								{}))
		self.actions.append(Action(
								"sync", 
								"synchroniser la télécommande", 
								self.sync, 
								{}))
		self.actions.append(Action(
								"unsync", 
								"désynchroniser la télécommande", 
								self.unsync, 
								{}))
		
	def set(self, driver, args):
		# TODO: vérifier la cohérence des arguments fournis avec ce qui a été demandé
		self.name = args['name']
		self.description = args['description']
		self.location = args['location']
		self.driver = driver
		
		self.house_code = args['house_code']
		self.group_code = args['group_code']
		self.unit_code = args['unit_code']
		
	def switch_on(self, args):
		#print"switch_on"
		self.driver.send_command(self, 1)

	def switch_off(self, args):
		self.driver.send_command(self, 0)
	
	def sync(self, args):
		for i in range(5):
			self.switch_on({})
			time.sleep(0.1)
	
	def unsync(self, args):
		for i in range(5):
			self.switch_off({})
			time.sleep(0.1)
	
	def update(self, new_command):
		retour = True
		if new_command == 1:
			self.informations[0].update("on")
		elif new_command == 0:
			self.informations[0].update("off")
		else:
			retour = "La nouvelle commande n'était ni un 1 ni un 0."
		return retour