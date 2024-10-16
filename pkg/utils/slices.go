package utils

func RemoveDuplicates(items interface{}) interface{} {
	uniqueItems := []interface{}{}
	seenItems := make(map[interface{}]bool)
	for _, item := range items.([]interface{}) {
		if _, ok := seenItems[item]; ok {
			continue
		}
		uniqueItems = append(uniqueItems, item)
		seenItems[item] = true
	}
	return uniqueItems
}
