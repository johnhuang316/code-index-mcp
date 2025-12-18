using Orders.Models;

namespace Orders.Repositories;

public interface IOrderRepository
{
    void Save(Order order);
    Order? Find(string id);
    void Update(Order order);
}

public class InMemoryOrderRepository : IOrderRepository
{
    private readonly Dictionary<string, Order> _store = new();

    public void Save(Order order) => _store[order.Id] = order;

    public Order? Find(string id) => _store.TryGetValue(id, out var order) ? order : null;

    public void Update(Order order) => _store[order.Id] = order;
}